"""Live worker metrics scraped from the RabbitMQ Management API.

Why a separate module: the broker is the authoritative source for
queue depth, unacknowledged messages, and dead-letter size. Going
through Celery's ``inspect.active()`` would add a broadcast round-trip
and only see workers that are actually online — the broker view stays
correct even when the worker pool is down (in fact, that's exactly when
queue_depth is most interesting).

Fail-closed: every error path resolves to ``None`` so the caller can
report ``broker_reachable: false`` and zeros to the client. ``/metrics``
must never 5xx because the broker is unreachable.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional, TypedDict
from urllib.parse import quote

import httpx

_logger = logging.getLogger(__name__)

# A 1.5s budget covers the usual RabbitMQ Management API latency
# (~10ms on the docker network) with plenty of headroom, while still
# keeping /metrics snappy if the broker is wedged. The endpoint is
# called from a polling admin page every 5s — we'd rather show stale
# zeros than block the dashboard render.
_MANAGEMENT_TIMEOUT_SECONDS = 1.5

_DEFAULT_MANAGEMENT_URL = "http://rabbitmq:15672"
_DEFAULT_USER = "apex"
_DEFAULT_VHOST = "apex"


class QueueStats(TypedDict):
    messages_ready: int
    messages_unacknowledged: int
    messages: int


def _management_base_url() -> str:
    return (
        os.environ.get("RABBITMQ_MANAGEMENT_URL", "").strip()
        or _DEFAULT_MANAGEMENT_URL
    ).rstrip("/")


def _credentials() -> tuple[str, str] | None:
    password = os.environ.get("RABBITMQ_PASSWORD", "").strip()
    if not password:
        return None
    user = os.environ.get("RABBITMQ_USER", _DEFAULT_USER).strip() or _DEFAULT_USER
    return user, password


def _vhost() -> str:
    return os.environ.get("RABBITMQ_VHOST", _DEFAULT_VHOST).strip() or _DEFAULT_VHOST


async def fetch_queue_stats(
    queue_name: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Optional[QueueStats]:
    """Query the Management API for a single queue.

    Returns ``None`` on any failure (no creds, HTTP error, missing
    fields). Callers treat ``None`` as "broker unreachable for this
    queue" and report zeros.

    The optional ``client`` parameter lets ``snapshot_worker_metrics``
    reuse one ``AsyncClient`` across both queue lookups instead of
    paying connection-setup cost twice.
    """
    creds = _credentials()
    if creds is None:
        return None

    base = _management_base_url()
    vhost = quote(_vhost(), safe="")
    queue = quote(queue_name, safe="")
    url = f"{base}/api/queues/{vhost}/{queue}"

    async def _do_get(c: httpx.AsyncClient) -> Optional[QueueStats]:
        try:
            response = await c.get(url, auth=creds, timeout=_MANAGEMENT_TIMEOUT_SECONDS)
        except (httpx.HTTPError, httpx.TimeoutException):
            _logger.debug("RabbitMQ management API unreachable for %s", queue_name, exc_info=True)
            return None
        if response.status_code != 200:
            _logger.debug(
                "RabbitMQ management API returned %s for %s", response.status_code, queue_name,
            )
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        # The API returns ints for these fields when the queue exists.
        # If the queue hasn't been declared yet (worker never started),
        # the GET 404s — handled by the status_code check above.
        try:
            return QueueStats(
                messages_ready=int(payload.get("messages_ready", 0)),
                messages_unacknowledged=int(payload.get("messages_unacknowledged", 0)),
                messages=int(payload.get("messages", 0)),
            )
        except (TypeError, ValueError):
            return None

    if client is not None:
        return await _do_get(client)
    async with httpx.AsyncClient() as owned_client:
        return await _do_get(owned_client)


async def snapshot_worker_metrics(
    *,
    main_queue: str = "apex.tasks",
    dead_queue: str = "apex.tasks.dead",
) -> dict[str, int | bool]:
    """Combine the two relevant queues into a single snapshot.

    Returns a dict shaped for the ``/metrics.workers`` block:

    - ``queue_depth``      → main queue ``messages_ready``
    - ``in_flight``        → main queue ``messages_unacknowledged`` (delivered to a worker, not yet acked)
    - ``dlq_size``         → dead-letter queue ``messages``
    - ``broker_reachable`` → ``true`` only if the main queue lookup succeeded

    A failure on either queue degrades that field to 0 without poisoning
    the whole snapshot, so a transient management-API blip on the DLQ
    doesn't blank out the live counters.
    """
    snapshot: dict[str, int | bool] = {
        "queue_depth": 0,
        "in_flight": 0,
        "dlq_size": 0,
        "broker_reachable": False,
    }

    async with httpx.AsyncClient() as client:
        main_stats, dead_stats = await asyncio.gather(
            fetch_queue_stats(main_queue, client=client),
            fetch_queue_stats(dead_queue, client=client),
        )

    if main_stats is not None:
        snapshot["queue_depth"] = main_stats["messages_ready"]
        snapshot["in_flight"] = main_stats["messages_unacknowledged"]
        snapshot["broker_reachable"] = True
    if dead_stats is not None:
        snapshot["dlq_size"] = dead_stats["messages"]

    return snapshot
