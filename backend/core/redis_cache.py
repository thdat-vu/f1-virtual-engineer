"""Shared Redis-backed cache for FastF1 helper outputs (#100 slice D).

Why this exists
---------------
Slice B added an in-process ``TTLCache``. That's great for one uvicorn
worker, but the moment we run multiple workers (`--workers 4`) or scale
horizontally to multiple pods, each process keeps its own cache — and the
same FastF1 query gets paid for N times in parallel.

This module provides a tiny opt-in second tier:

* L1 (in-process) — `cachetools.TTLCache`, owned by `tools/fastf1_helper.py`.
* L2 (shared)     — Redis, namespaced under ``f1:cache:<helper>:<digest>``.

Lookup order in the wrapper is L1 → L2 → compute. On a compute we write to
both. A Redis outage degrades silently to "L1 only" — the API never 5xxs
because of cache infrastructure.

Opt-in / fail-closed semantics
------------------------------
* Set ``REDIS_URL`` (e.g. ``redis://localhost:6379/0``) to enable.
* Leave it blank to fully disable. No connection attempt is made.
* If a connect fails on first use, the client is pinned to ``None`` for
  the process lifetime; subsequent calls return immediately. This is a
  crude "open circuit". A long-running app that wants to recover after a
  Redis restart should `reset_for_tests()` (despite the name) or restart.
* Every GET/SET is wrapped in a broad except — a Redis hiccup must not
  break the response path.

Not goals for this slice
------------------------
* Distributed locking / single-flight (slice D-C from the docs note).
* Rate-limit backend swap (slice D-B).
* Background workers / Redis Streams (slice D-D).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover — redis is a runtime dep
    redis = None  # type: ignore

_logger = logging.getLogger(__name__)

# Module-level memoised client. None means "either not configured or the
# last init failed and we've given up for this process". Tests reset this
# via reset_for_tests().
_client: Any = None
_init_attempted: bool = False

# Key shape: f1:cache:<namespace>:<digest>. The "f1:cache:" prefix lets
# operators namespace this app inside a shared Redis without collisions.
_KEY_PREFIX = "f1:cache:"


def _build_client() -> Any:
    """Create a Redis client from REDIS_URL. Returns None when disabled."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url or redis is None:
        return None
    try:
        # Short timeouts keep a dead Redis from inflating request latency
        # past what FastF1 itself adds on a cold load. 500ms is generous
        # for a healthy Redis on the same network and tolerable as a
        # one-time per-request penalty when it's broken.
        client = redis.Redis.from_url(
            url,
            socket_timeout=0.5,
            socket_connect_timeout=0.5,
            decode_responses=False,
        )
        # PING up-front so we surface misconfiguration at startup rather
        # than on the first user request.
        client.ping()
        return client
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning(
            "Redis init failed for REDIS_URL=%r; falling back to in-process cache only",
            url,
            exc_info=True,
        )
        return None


def _get_client() -> Any:
    global _client, _init_attempted
    if _init_attempted:
        return _client
    _init_attempted = True
    _client = _build_client()
    return _client


def is_enabled() -> bool:
    """For diagnostics — has Redis been successfully wired up?"""
    return _get_client() is not None


def _redis_key(namespace: str, key: str) -> str:
    return f"{_KEY_PREFIX}{namespace}:{key}"


def get(namespace: str, key: str) -> Any | None:
    """Return the cached value or None on miss / error / disabled."""
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(_redis_key(namespace, key))
    except Exception:  # noqa: BLE001
        _logger.warning("Redis GET failed for %s/%s", namespace, key, exc_info=True)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        # Corrupt or non-JSON payload — log and treat as miss.
        _logger.warning("Redis payload for %s/%s was not JSON", namespace, key)
        return None


def set(namespace: str, key: str, value: Any, ttl_seconds: int) -> None:
    """Persist a value for ttl_seconds. Silent no-op when disabled or errored."""
    client = _get_client()
    if client is None:
        return
    try:
        payload = json.dumps(value, default=str)
        client.set(_redis_key(namespace, key), payload, ex=ttl_seconds)
    except Exception:  # noqa: BLE001
        _logger.warning("Redis SET failed for %s/%s", namespace, key, exc_info=True)


def reset_for_tests() -> None:
    """Wipe the memoised client so the next call re-reads REDIS_URL.

    Despite the name, it's also useful in long-running deployments after
    operators reset Redis state out-of-band — but in production, expect
    to restart the app instead.
    """
    global _client, _init_attempted
    _client = None
    _init_attempted = False
