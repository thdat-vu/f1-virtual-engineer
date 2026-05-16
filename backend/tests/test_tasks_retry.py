"""Retry + DLQ tests for the Celery scaffold (#139 PR2).

Tests run with ``CELERY_TASK_ALWAYS_EAGER=true``. Two important caveats
that drive how these tests are shaped:

1. In eager mode, ``task.apply()`` does NOT loop retries — Celery
   raises a ``Retry`` exception once and stops. So we can't drive a
   "fail twice then succeed" assertion through ``.apply()``. Instead we
   pin the retry policy by reading the task config (``max_retries``,
   ``autoretry_for``, etc).
2. The DLQ fan-out lives in ``TaskWithDLQ.on_failure``. We exercise it
   directly with the terminal exception types Celery would actually
   raise (``MaxRetriesExceededError``, ``PermanentError``) and patch
   ``app.send_task`` to capture what would have been published.

This keeps the tests broker-free without sacrificing coverage of the
behavior we actually care about.
"""

from __future__ import annotations

import importlib
import logging
import os
import unittest
from unittest.mock import patch

from celery.exceptions import MaxRetriesExceededError, Retry


class _TasksUnderTest:
    """Lazily-imported handle to the tasks package after env setup."""

    def __init__(self) -> None:
        os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
        for mod in (
            "tasks.dlq_consumer",
            "tasks.example",
            "tasks.exceptions",
            "tasks",
        ):
            if mod in importlib.sys.modules:
                del importlib.sys.modules[mod]
        self.tasks = importlib.import_module("tasks")
        self.example = importlib.import_module("tasks.example")
        self.dlq = importlib.import_module("tasks.dlq_consumer")
        self.exceptions = importlib.import_module("tasks.exceptions")


class RetryConfigTests(unittest.TestCase):
    """Pin the retry policy declaratively — eager mode can't loop retries."""

    def setUp(self) -> None:
        self.h = _TasksUnderTest()

    def test_flaky_ping_has_three_max_retries(self) -> None:
        self.assertEqual(self.h.example.flaky_ping.max_retries, 3)

    def test_flaky_ping_uses_taskwithdlq_base(self) -> None:
        self.assertIsInstance(self.h.example.flaky_ping, self.h.tasks.TaskWithDLQ)

    def test_flaky_ping_autoretries_only_on_transient(self) -> None:
        autoretry = self.h.example.flaky_ping.autoretry_for or ()
        self.assertIn(self.h.exceptions.TransientError, autoretry)
        # PermanentError must NOT be in autoretry_for, otherwise we'd
        # retry on schema/logic errors that won't get better.
        self.assertNotIn(self.h.exceptions.PermanentError, autoretry)

    def test_flaky_ping_uses_exponential_backoff_with_jitter(self) -> None:
        # retry_backoff is the base — Celery multiplies it by 2 ** attempt.
        self.assertEqual(self.h.example.flaky_ping.retry_backoff, 2)
        self.assertEqual(self.h.example.flaky_ping.retry_backoff_max, 60)
        self.assertTrue(self.h.example.flaky_ping.retry_jitter)


class TransientRetryEagerTests(unittest.TestCase):
    """Eager-mode behavior: a TransientError surfaces as ``Retry``."""

    def setUp(self) -> None:
        self.h = _TasksUnderTest()
        self.h.example.reset_flaky_counters()

    def test_first_transient_failure_raises_retry_in_eager_mode(self) -> None:
        # In eager mode, autoretry_for catches the TransientError and
        # converts it to a Retry signal. The result wrapper surfaces
        # that as a celery.exceptions.Retry — proof that the retry
        # path is wired up, even though the loop itself runs on a real
        # broker rather than inline.
        with self.assertRaises(Retry):
            self.h.example.flaky_ping.apply(args=("once", 1)).get()


class DLQFanOutTests(unittest.TestCase):
    """``TaskWithDLQ.on_failure`` publishes terminal failures to the DLQ."""

    def setUp(self) -> None:
        self.h = _TasksUnderTest()

    def _trigger_on_failure(self, task, exc) -> dict:
        with patch.object(self.h.tasks.app, "send_task") as send_task:
            task.on_failure(
                exc,
                "task-id-abc",
                ("arg1",),
                {"k": "v"},
                None,
            )
        send_task.assert_called_once()
        call = send_task.call_args
        return {
            "name": call.args[0] if call.args else call.kwargs.get("name", ""),
            "queue": call.kwargs.get("queue"),
            "envelope": call.kwargs.get("kwargs", {}),
        }

    def test_max_retries_exceeded_lands_in_dlq(self) -> None:
        exc = MaxRetriesExceededError("3/3 retries exhausted")
        published = self._trigger_on_failure(self.h.example.flaky_ping, exc)
        self.assertEqual(published["queue"], self.h.tasks.DEAD_QUEUE)
        envelope = published["envelope"]
        self.assertEqual(envelope["origin_task"], "tasks.example.flaky_ping")
        self.assertEqual(envelope["origin_task_id"], "task-id-abc")
        self.assertEqual(envelope["exc_type"], "MaxRetriesExceededError")

    def test_permanent_error_lands_in_dlq(self) -> None:
        exc = self.h.exceptions.PermanentError("schema mismatch")
        published = self._trigger_on_failure(self.h.example.always_broken, exc)
        envelope = published["envelope"]
        self.assertEqual(envelope["origin_task"], "tasks.example.always_broken")
        self.assertEqual(envelope["exc_type"], "PermanentError")
        self.assertIn("schema mismatch", envelope["exc_msg"])

    def test_pending_retry_does_not_land_in_dlq(self) -> None:
        # A bare TransientError reaching on_failure during an in-flight
        # retry must NOT trigger the DLQ — that's still on the retry
        # path. Only terminal exceptions should fan out.
        with patch.object(self.h.tasks.app, "send_task") as send_task:
            self.h.example.flaky_ping.on_failure(
                self.h.exceptions.TransientError("still going"),
                "task-id-xyz",
                ("arg",),
                {},
                None,
            )
        send_task.assert_not_called()

    def test_dlq_publish_failure_is_swallowed(self) -> None:
        # Best-effort: if the broker is itself unhealthy at the moment
        # we try to enqueue the DLQ entry, on_failure must not raise —
        # raising would mask the original task error or crash the worker.
        with patch.object(
            self.h.tasks.app, "send_task", side_effect=RuntimeError("broker down")
        ):
            self.h.example.flaky_ping.on_failure(
                MaxRetriesExceededError("done"),
                "task-id-zzz",
                (),
                {},
                None,
            )
        # No exception -> pass. The structured "Failed to enqueue DLQ
        # entry" log line is the operator's only signal here.


class DLQConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.h = _TasksUnderTest()
        os.environ["DLQ_BUMP_COUNTER"] = "false"
        self.addCleanup(lambda: os.environ.pop("DLQ_BUMP_COUNTER", None))

    def test_process_failure_returns_envelope_with_required_fields(self) -> None:
        envelope = self.h.dlq.process_failure(
            origin_task="tasks.example.flaky_ping",
            origin_task_id="abc-123",
            args=["doomed"],
            kwargs={"foo": "bar"},
            exc_type="MaxRetriesExceededError",
            exc_msg="3/3 retries exhausted",
        )
        self.assertEqual(envelope["event"], "task.dead_letter")
        self.assertEqual(envelope["origin_task"], "tasks.example.flaky_ping")
        self.assertEqual(envelope["origin_task_id"], "abc-123")
        self.assertEqual(envelope["exc_type"], "MaxRetriesExceededError")
        self.assertIn("retries exhausted", envelope["exc_msg"])

    def test_process_failure_emits_structured_error_log(self) -> None:
        with self.assertLogs("tasks.dlq", level=logging.ERROR) as cm:
            self.h.dlq.process_failure(
                origin_task="tasks.example.always_broken",
                origin_task_id="xyz",
                args=[],
                kwargs={},
                exc_type="PermanentError",
                exc_msg="bad input",
            )
        # Single line, JSON-shaped, with the canonical event name. The
        # log shipper builds alerts on this string — keep it stable.
        self.assertEqual(len(cm.output), 1)
        self.assertIn("task.dead_letter", cm.output[0])
        self.assertIn("PermanentError", cm.output[0])

    def test_process_failure_stringifies_non_json_args(self) -> None:
        # Real workloads will sometimes pass a set / datetime / dataclass
        # in args — the envelope must not crash the JSON serializer.
        envelope = self.h.dlq.process_failure(
            origin_task="tasks.example.always_broken",
            origin_task_id="xyz",
            args=[{1, 2, 3}],
            kwargs={"obj": object()},
            exc_type="PermanentError",
            exc_msg="x",
        )
        self.assertEqual(len(envelope["args"]), 1)
        self.assertEqual(len(envelope["kwargs"]), 1)


class TopologyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.h = _TasksUnderTest()

    def test_dead_queue_is_registered(self) -> None:
        queue_names = {q.name for q in self.h.tasks.app.conf.task_queues}
        self.assertIn(self.h.tasks.DEFAULT_QUEUE, queue_names)
        self.assertIn(self.h.tasks.DEAD_QUEUE, queue_names)

    def test_default_queue_has_bounded_length(self) -> None:
        for q in self.h.tasks.app.conf.task_queues:
            if q.name == self.h.tasks.DEFAULT_QUEUE:
                args = q.queue_arguments or {}
                self.assertEqual(args.get("x-max-length"), 10000)
                self.assertEqual(args.get("x-overflow"), "reject-publish")
                return
        self.fail("default queue not found")

    def test_dlq_consumer_task_registered(self) -> None:
        self.assertIn("tasks.dlq.process_failure", self.h.tasks.app.tasks)


if __name__ == "__main__":
    unittest.main()
