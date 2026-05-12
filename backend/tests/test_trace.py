import unittest

from core.trace import clear_trace, get_trace, record, start_trace, traced


class TraceTests(unittest.TestCase):
    def setUp(self):
        clear_trace()

    def tearDown(self):
        clear_trace()

    def test_get_trace_returns_empty_when_inactive(self):
        self.assertEqual(get_trace(), [])

    def test_start_trace_initialises_empty_list(self):
        entries = start_trace()
        self.assertEqual(entries, [])
        self.assertIs(get_trace(), entries)

    def test_record_appends_when_trace_active(self):
        start_trace()
        record("telemetry", 12.345, status="ok")
        record("strategy", 6.7, status="ok")

        trace = get_trace()
        self.assertEqual(len(trace), 2)
        self.assertEqual(trace[0]["tool"], "telemetry")
        self.assertEqual(trace[0]["duration_ms"], 12.35)
        self.assertEqual(trace[0]["status"], "ok")
        self.assertEqual(trace[1]["tool"], "strategy")

    def test_record_is_noop_when_trace_inactive(self):
        record("telemetry", 1.0)
        self.assertEqual(get_trace(), [])

    def test_traced_decorator_records_success(self):
        @traced("demo")
        def work(x: int) -> int:
            return x * 2

        start_trace()
        self.assertEqual(work(3), 6)
        trace = get_trace()
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["tool"], "demo")
        self.assertEqual(trace[0]["status"], "ok")
        self.assertGreaterEqual(trace[0]["duration_ms"], 0.0)

    def test_traced_decorator_records_error_and_reraises(self):
        @traced("boom")
        def explode() -> None:
            raise ValueError("nope")

        start_trace()
        with self.assertRaises(ValueError):
            explode()

        trace = get_trace()
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["tool"], "boom")
        self.assertEqual(trace[0]["status"], "error")

    def test_traced_decorator_noop_when_no_trace_active(self):
        @traced("demo")
        def work() -> int:
            return 1

        self.assertEqual(work(), 1)
        self.assertEqual(get_trace(), [])


if __name__ == "__main__":
    unittest.main()
