"""DLQ consumer task — runs on the dlq-worker service (#139 PR2).

The dlq-worker is a separate container that consumes ``apex.tasks.dead``
exclusively. When a regular task exhausts retries or hits a
``PermanentError``, ``TaskWithDLQ.on_failure`` enqueues a synthetic
``tasks.dlq.process_failure`` task here with a diagnostic envelope.

What this consumer does:

1. Emit a single structured ``ERROR`` log line per landing — fields are
   stable so log shipping / grep can build alerts on them.
2. Bump a Redis counter ``workers:failed_24h`` (24-hour rolling window
   via key TTL). The ``/metrics`` endpoint reads this (PR3) to surface
   ``workers.failed_24h`` so the operator notices when the DLQ is
   filling.

We deliberately do NOT auto-retry from here. The DLQ exists precisely
because automatic retries already failed; a human (or a follow-up tool)
should look at the entry. If you find yourself wanting to retry from
the DLQ, file an issue — the design has shifted.

The companion success counter (``workers:completed_24h``) is bumped
from the Celery ``task_success`` signal handler in :mod:`tasks` — see
that module for the wiring.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from tasks import app


logger = logging.getLogger("tasks.dlq")


_DLQ_COUNTER_KEY = "workers:failed_24h"
_SUCCESS_COUNTER_KEY = "workers:completed_24h"
_COUNTER_TTL_SECONDS = 24 * 60 * 60


def _bump_counter(key: str) -> None:
    """Best-effort increment of a 24h-rolling Redis counter.

    Imported lazily so this module loads even when redis is unavailable
    (CI without a broker, eager-mode unit tests). A Redis outage must
    never mask the failure or break a task — the structured log line
    (for failures) and the task return value (for successes) remain the
    sources of truth.
    """

    try:
        from core import redis_cache
    except Exception:  # noqa: BLE001
        return

    if not redis_cache.is_enabled():
        return

    try:
        client = redis_cache._get_client()
        if client is None:
            return
        new_value = client.incr(key)
        # Only set TTL on first increment; subsequent calls are no-ops
        # because the key already exists. ``new_value == 1`` is the
        # documented signal that this is a fresh key.
        if new_value == 1:
            client.expire(key, _COUNTER_TTL_SECONDS)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to bump counter %s; metric will under-count.", key)


def _bump_failure_counter() -> None:
    _bump_counter(_DLQ_COUNTER_KEY)


def bump_success_counter() -> None:
    """Public hook used by the ``task_success`` signal in :mod:`tasks`."""
    _bump_counter(_SUCCESS_COUNTER_KEY)


@app.task(name="tasks.dlq.process_failure")
def process_failure(
    origin_task: str,
    origin_task_id: str,
    args: list[Any],
    kwargs: dict[str, Any],
    exc_type: str,
    exc_msg: str,
) -> dict[str, Any]:
    """Receive a terminal-failure envelope, log + count.

    Returns the same envelope so a future tool (or a test) can inspect
    what was processed without going back to the broker.
    """

    envelope = {
        "event": "task.dead_letter",
        "origin_task": origin_task,
        "origin_task_id": origin_task_id,
        "exc_type": exc_type,
        "exc_msg": exc_msg,
        # Stringify args/kwargs so a downstream JSON log shipper doesn't
        # choke on non-serializable types (datetimes, sets, etc.).
        "args": [repr(a) for a in args],
        "kwargs": {k: repr(v) for k, v in kwargs.items()},
    }
    # ``logger.error(...)`` with a single JSON-serialized message gives
    # us greppable / alertable output without taking a dependency on a
    # structured-logging library yet.
    logger.error(json.dumps(envelope, separators=(",", ":")))

    if os.getenv("DLQ_BUMP_COUNTER", "true").lower() in {"1", "true", "yes", "on"}:
        _bump_failure_counter()

    return envelope


__all__ = ["process_failure", "bump_success_counter"]
