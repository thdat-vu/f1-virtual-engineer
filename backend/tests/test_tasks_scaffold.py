"""Smoke tests for the Celery scaffold (#139 PR1).

These run inside CI without a real broker by using
``CELERY_TASK_ALWAYS_EAGER=true`` — the task executes inline in the
calling process and ``.delay()`` returns a synchronous result wrapper.
"""

from __future__ import annotations

import importlib
import os
import unittest


class CelerySmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Toggle eager mode BEFORE importing tasks.* so the env-driven
        # default in tasks.app picks it up. Re-import on each test class
        # in case a previous test imported the module without the flag.
        os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
        cls._tasks = importlib.import_module("tasks")
        cls._example = importlib.import_module("tasks.example")
        importlib.reload(cls._tasks)
        importlib.reload(cls._example)

    def test_app_is_celery_instance(self) -> None:
        from celery import Celery

        self.assertIsInstance(self._tasks.app, Celery)

    def test_app_runs_in_eager_mode(self) -> None:
        # Eager mode is the only thing keeping these tests broker-free.
        # If a future change accidentally flips it off in this code path,
        # the tests would hang trying to reach a broker — fail loudly
        # instead.
        self.assertTrue(self._tasks.app.conf.task_always_eager)

    def test_ping_task_registered_under_canonical_name(self) -> None:
        self.assertIn("tasks.example.ping", self._tasks.app.tasks)

    def test_ping_runs_inline_via_delay(self) -> None:
        result = self._example.ping.delay("hi")
        self.assertEqual(result.get(timeout=1), "pong: hi")

    def test_ping_runs_inline_via_call(self) -> None:
        # Direct call should work too — useful for unit-testing task
        # logic without going through the eager scheduler.
        self.assertEqual(self._example.ping("world"), "pong: world")


if __name__ == "__main__":
    unittest.main()
