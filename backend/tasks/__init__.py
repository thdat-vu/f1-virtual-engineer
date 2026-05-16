"""Celery app factory for #139 — async task pipeline scaffold.

The factory is intentionally tolerant: it imports cleanly even when the
broker/result-backend env vars are blank, so importing ``tasks`` from
the FastAPI process (e.g. to call ``ping.delay(...)``) does not crash on
boot. Only ``.delay()`` / ``.apply_async()`` will fail loudly when the
broker is missing — and that's the failure mode we actually want.

Configuration knobs (all read from env, defaults safe for CI):

- ``CELERY_BROKER_URL`` — e.g. ``amqp://apex:<pass>@rabbitmq:5672/``.
  When unset, Celery defaults to ``amqp://guest@localhost//`` which will
  refuse to connect from inside the container; that's fine for the
  scaffold since no synchronous code path enqueues yet.
- ``CELERY_RESULT_BACKEND`` — e.g. ``redis://:<pass>@redis:6379/1``.
  Distinct DB index from the L2 cache (db 0) so a ``FLUSHDB`` on either
  side can't wipe the other.
- ``CELERY_TASK_ALWAYS_EAGER`` — set to ``true`` in unit tests so tasks
  run inline without a broker.

Topology (#139 PR2):

- Main queue ``apex.tasks`` is bounded — ``x-max-length=10000`` plus
  ``x-overflow=reject-publish`` so a runaway producer sees ``MessageNack``
  rather than filling the disk. Same defensive pattern as Redis's
  ``maxmemory + allkeys-lru``.
- A separate dead-letter queue ``apex.tasks.dead`` receives a synthetic
  ``tasks.dlq.process_failure`` task whenever a regular task exhausts
  retries or raises ``PermanentError``. The dlq-worker drains it,
  emits a structured log line, and bumps a Redis counter the
  ``/metrics`` endpoint will read in PR3.
- Bypass via on_failure (rather than RabbitMQ-native dead-lettering on
  reject) is deliberate: it works identically in eager mode for tests,
  doesn't depend on broker-specific behavior, and lets us attach a
  rich diagnostic envelope to the DLQ message.
"""

from __future__ import annotations

import logging
import os

from celery import Celery, Task
from celery.exceptions import MaxRetriesExceededError
from kombu import Exchange, Queue

from tasks.exceptions import PermanentError


logger = logging.getLogger(__name__)


DEFAULT_QUEUE = "apex.tasks"
DEAD_QUEUE = "apex.tasks.dead"


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "")
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


app = Celery(
    "apex",
    broker=os.getenv("CELERY_BROKER_URL", ""),
    backend=os.getenv("CELERY_RESULT_BACKEND", ""),
    include=["tasks.example", "tasks.dlq_consumer"],
)


_default_exchange = Exchange(DEFAULT_QUEUE, type="direct")
_dead_exchange = Exchange(DEAD_QUEUE, type="direct")


app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_always_eager=_bool_env("CELERY_TASK_ALWAYS_EAGER"),
    task_eager_propagates=True,
    task_default_queue=DEFAULT_QUEUE,
    task_default_exchange=DEFAULT_QUEUE,
    task_default_routing_key=DEFAULT_QUEUE,
    task_queues=(
        Queue(
            DEFAULT_QUEUE,
            exchange=_default_exchange,
            routing_key=DEFAULT_QUEUE,
            queue_arguments={
                "x-max-length": 10000,
                "x-overflow": "reject-publish",
            },
        ),
        Queue(
            DEAD_QUEUE,
            exchange=_dead_exchange,
            routing_key=DEAD_QUEUE,
        ),
    ),
)


class TaskWithDLQ(Task):
    """Base for tasks that should fan failures out to the DLQ.

    On terminal failure (retries exhausted, or any ``PermanentError``),
    publishes a ``tasks.dlq.process_failure`` task to the dead queue
    carrying a diagnostic envelope. The DLQ consumer takes it from
    there.

    Transient failures that are still going to be retried do NOT trigger
    the DLQ path — Celery calls ``on_failure`` after each retry attempt
    too, so we filter on ``MaxRetriesExceededError`` / ``PermanentError``
    explicitly.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # type: ignore[override]
        is_terminal = isinstance(exc, (MaxRetriesExceededError, PermanentError))
        if is_terminal:
            try:
                app.send_task(
                    "tasks.dlq.process_failure",
                    kwargs={
                        "origin_task": self.name,
                        "origin_task_id": task_id,
                        "args": list(args) if args else [],
                        "kwargs": dict(kwargs) if kwargs else {},
                        "exc_type": type(exc).__name__,
                        "exc_msg": str(exc),
                    },
                    queue=DEAD_QUEUE,
                    routing_key=DEAD_QUEUE,
                )
            except Exception:  # noqa: BLE001
                # Best-effort: a broken DLQ must not mask the original
                # failure or block the worker.
                logger.exception(
                    "Failed to enqueue DLQ entry for task=%s id=%s", self.name, task_id
                )
        return super().on_failure(exc, task_id, args, kwargs, einfo)


__all__ = ["app", "TaskWithDLQ", "DEFAULT_QUEUE", "DEAD_QUEUE"]
