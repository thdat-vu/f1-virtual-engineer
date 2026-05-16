"""Smoke-test tasks for the Celery scaffold.

``ping`` exists so we can verify the worker is wired up end-to-end
before porting any real workload (the LLM rationale path lands in PR3
of #139). Inside the worker container:

    python -c "from tasks.example import ping; print(ping.delay('hi').get(timeout=5))"

should print ``pong: hi``.

``flaky_ping`` exercises the retry policy + DLQ topology added in PR2 —
fail ``fail_n_times`` times then succeed, or fail forever if
``fail_n_times`` exceeds ``max_retries``. Used by the test suite to
prove transient failures auto-retry and terminal failures land in the
dead queue.
"""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict

from tasks import TaskWithDLQ, app
from tasks.exceptions import PermanentError, TransientError


@app.task(name="tasks.example.ping")
def ping(text: str) -> str:
    return f"pong: {text}"


# Per-task-id call counter, shared between retries. Module-level state
# is fine here because eager mode runs in-process; in the broker-backed
# path each retry hits the same worker key anyway and even if it didn't,
# this task is only used by tests.
_FLAKY_CALLS: DefaultDict[str, int] = defaultdict(int)


@app.task(
    name="tasks.example.flaky_ping",
    bind=True,
    base=TaskWithDLQ,
    autoretry_for=(TransientError,),
    max_retries=3,
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
)
def flaky_ping(self, key: str, fail_n_times: int) -> str:
    """Fail transiently ``fail_n_times`` times, then return ``pong: <key>``.

    With ``fail_n_times <= 3`` (the configured ``max_retries``) the task
    eventually succeeds. With ``fail_n_times > 3`` it exhausts retries,
    and ``TaskWithDLQ.on_failure`` fans the failure out to the DLQ.
    """

    _FLAKY_CALLS[key] += 1
    if _FLAKY_CALLS[key] <= fail_n_times:
        raise TransientError(f"call {_FLAKY_CALLS[key]} for {key} failed transiently")
    return f"pong: {key}"


@app.task(
    name="tasks.example.always_broken",
    base=TaskWithDLQ,
)
def always_broken(reason: str) -> str:
    """Always raises ``PermanentError`` — lands in DLQ on first failure.

    Used by tests to prove ``PermanentError`` skips retry entirely.
    """

    raise PermanentError(f"this task is permanently broken: {reason}")


def reset_flaky_counters() -> None:
    """Test helper — wipes per-key call counts between cases."""

    _FLAKY_CALLS.clear()
