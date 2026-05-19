"""Idempotency-Key dedupe for POST /analyze (#161).

Why a separate module: the /analyze hot path already merges auth, rate
limiting, agent execution, persistence, and async enqueue. Squeezing
idempotency in-line would push that handler past its readability budget,
and we'd lose the single test surface.

Behavior:
- Caller passes ``Idempotency-Key: <uuid>`` header. Absent header → no
  caching path; the request runs normally.
- Server writes ``{status: "pending", ts}`` under the key with a 60s
  TTL **before** invoking the agent (SETNX so two simultaneous requests
  with the same key don't both run).
- On agent completion the server overwrites the entry with
  ``{status: "done", payload}``.
- Subsequent requests within the TTL see ``status: "done"`` and return
  the cached payload without re-running the agent.

Fail-open: any Redis error (unreachable, malformed payload, etc.) is
swallowed; the request runs as if no cache existed. /analyze must never
5xx because the dedupe layer is unhealthy.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core import redis_cache

_logger = logging.getLogger(__name__)

NAMESPACE = "idem:analyze"
TTL_SECONDS = 60

# Status values written under the key.
STATUS_PENDING = "pending"
STATUS_DONE = "done"


def _redis_key(idempotency_key: str) -> str:
    return f"{NAMESPACE}:{idempotency_key}"


def lookup(idempotency_key: str) -> tuple[str, Any] | None:
    """Return the cached entry for the key, or None on miss/error.

    The tuple is ``(status, payload)``. ``payload`` is ``None`` for
    pending entries and the cached response dict for done entries.
    """
    client = redis_cache._get_client()
    if client is None:
        return None
    try:
        raw = client.get(_redis_key(idempotency_key))
    except Exception:  # noqa: BLE001 — fail-open
        _logger.warning("Idempotency lookup failed", exc_info=True)
        return None
    if raw is None:
        return None
    try:
        entry = json.loads(raw)
    except ValueError:
        return None
    status = entry.get("status")
    if status == STATUS_PENDING:
        return STATUS_PENDING, None
    if status == STATUS_DONE:
        return STATUS_DONE, entry.get("payload")
    return None


def reserve(idempotency_key: str) -> bool:
    """Atomically claim the key for a fresh run.

    Returns ``True`` if this caller is the writer; ``False`` if another
    request already holds the key (caller should treat it as a pending
    duplicate). Fail-open: a Redis blip returns ``True`` so the request
    proceeds without caching.
    """
    client = redis_cache._get_client()
    if client is None:
        return True
    try:
        payload = json.dumps({"status": STATUS_PENDING})
        # NX + EX in one call — atomic, no race between two identical keys.
        ok = client.set(_redis_key(idempotency_key), payload, ex=TTL_SECONDS, nx=True)
        return bool(ok)
    except Exception:  # noqa: BLE001 — fail-open
        _logger.warning("Idempotency reserve failed", exc_info=True)
        return True


def commit(idempotency_key: str, payload: dict[str, Any]) -> None:
    """Replace the pending entry with the final response payload.

    TTL is reset to TTL_SECONDS — the window during which retries may
    short-circuit. Fail-closed semantics here would make the hot path
    flakier, so we still swallow Redis errors; the worst case is a
    client retry that re-runs the agent (the same as having no cache
    at all, which is what the rest of the codebase already tolerates).
    """
    client = redis_cache._get_client()
    if client is None:
        return
    try:
        body = json.dumps(
            {"status": STATUS_DONE, "payload": payload},
            default=str,
        )
        client.set(_redis_key(idempotency_key), body, ex=TTL_SECONDS)
    except Exception:  # noqa: BLE001 — fail-open
        _logger.warning("Idempotency commit failed", exc_info=True)


def release(idempotency_key: str) -> None:
    """Drop the pending entry when the agent run errored.

    Without this, a 500 response would leave the key locked for the
    full TTL — the user retrying would get 409 instead of a fresh run.
    """
    client = redis_cache._get_client()
    if client is None:
        return
    try:
        client.delete(_redis_key(idempotency_key))
    except Exception:  # noqa: BLE001 — fail-open
        _logger.warning("Idempotency release failed", exc_info=True)
