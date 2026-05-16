"""Tests for the async LLM rationale back-fill task (#139 PR3).

Like the other task-level tests, these run with
``CELERY_TASK_ALWAYS_EAGER=true`` so we can drive the task synchronously
without needing a real broker. The interesting bits are:

- ``generate_rationale`` is monkeypatched so we don't reach for a real
  Gemini key — and so we can deterministically simulate
  outage / quota cases.
- ``update_analyze_history_rationale`` is monkeypatched so we can assert
  on what the worker would have written without provisioning a Supabase
  project for CI. The patched coroutine returns ``True`` (row updated)
  or ``False`` (no row updated, e.g. already upgraded) at our discretion.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import unittest
from unittest.mock import patch

from celery.exceptions import Retry


def _load_tasks() -> tuple[object, object, object, object]:
    """Fresh-import the tasks package after env setup."""

    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    for mod in (
        "tasks.rationale",
        "tasks.dlq_consumer",
        "tasks.example",
        "tasks.exceptions",
        "tasks",
    ):
        if mod in sys.modules:
            del sys.modules[mod]
    tasks = importlib.import_module("tasks")
    rationale = importlib.import_module("tasks.rationale")
    exceptions = importlib.import_module("tasks.exceptions")
    return tasks, rationale, exceptions, importlib.import_module("tasks.example")


async def _async_true(*args, **kwargs):
    return True


async def _async_false(*args, **kwargs):
    return False


class RationaleTaskHappyPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks, self.rationale_mod, self.exceptions, _ = _load_tasks()

    def test_backfill_writes_rationale_and_reports_updated(self) -> None:
        with (
            patch("core.llm.generate_rationale", return_value="VER pace was strong all stint."),
            patch("core.persistence.update_analyze_history_rationale", side_effect=_async_true) as upd,
        ):
            result = self.rationale_mod.backfill_rationale.apply(
                args=("row-123", "user-1", {"intent": {}, "telemetry_data": {}}),
            ).get()

        self.assertEqual(result, {"updated": True, "row_id": "row-123"})
        upd.assert_called_once()
        # Sanity-check that the LLM text propagated through to the patch
        # call rather than being dropped silently.
        kwargs = upd.call_args.kwargs
        self.assertEqual(kwargs["row_id"], "row-123")
        self.assertEqual(kwargs["user_id"], "user-1")
        self.assertIn("VER", kwargs["rationale_text"])

    def test_idempotent_no_op_when_row_already_upgraded(self) -> None:
        # The persistence helper filters on rationale_source=eq.template,
        # so a re-delivered task on a row that's already llm gets False
        # back. The task must report updated=False rather than fail.
        with (
            patch("core.llm.generate_rationale", return_value="anything"),
            patch("core.persistence.update_analyze_history_rationale", side_effect=_async_false),
        ):
            result = self.rationale_mod.backfill_rationale.apply(
                args=("row-123", "user-1", {}),
            ).get()

        self.assertEqual(result, {"updated": False, "row_id": "row-123"})


class RationaleTaskFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks, self.rationale_mod, self.exceptions, _ = _load_tasks()

    def test_empty_row_id_raises_permanent_error(self) -> None:
        # Bad enqueue (we shipped a row_id="" by mistake) is permanent —
        # retrying won't make it valid. The DLQ fan-out for any
        # PermanentError is covered by ``TaskWithDLQ`` in
        # ``test_tasks_retry``; here we just verify this task raises
        # the right exception class for that machinery to fire on.
        with self.assertRaises(self.exceptions.PermanentError):
            self.rationale_mod.backfill_rationale.apply(
                args=("", "user-1", {}),
            ).get()

    def test_llm_unavailable_signals_transient_retry(self) -> None:
        # generate_rationale returning None means Gemini declined to
        # produce output (network blip, quota). The task must signal a
        # transient retry — eager mode surfaces that as a Retry exception.
        with (
            patch("core.llm.generate_rationale", return_value=None),
            patch("core.persistence.update_analyze_history_rationale", side_effect=_async_true),
        ):
            with self.assertRaises(Retry):
                self.rationale_mod.backfill_rationale.apply(
                    args=("row-1", "user-1", {}),
                ).get()


class RationaleTaskRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks, self.rationale_mod, _, _ = _load_tasks()

    def test_task_registered_under_canonical_name(self) -> None:
        self.assertIn("tasks.rationale.backfill_rationale", self.tasks.app.tasks)

    def test_task_uses_taskwithdlq_base(self) -> None:
        self.assertIsInstance(
            self.rationale_mod.backfill_rationale, self.tasks.TaskWithDLQ
        )

    def test_task_has_three_retries_with_backoff(self) -> None:
        self.assertEqual(self.rationale_mod.backfill_rationale.max_retries, 3)
        self.assertEqual(self.rationale_mod.backfill_rationale.retry_backoff, 2)
        self.assertTrue(self.rationale_mod.backfill_rationale.retry_jitter)


if __name__ == "__main__":
    unittest.main()
