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
"""

from __future__ import annotations

import os

from celery import Celery


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "")
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


app = Celery(
    "apex",
    broker=os.getenv("CELERY_BROKER_URL", ""),
    backend=os.getenv("CELERY_RESULT_BACKEND", ""),
    include=["tasks.example"],
)

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
)


__all__ = ["app"]
