"""Tests for the request-timing middleware + /metrics endpoint (#100)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from core.timing import reset_metrics_for_tests, snapshot_metrics


class TimingMiddlewareTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_metrics_for_tests()
        self.client = TestClient(app)

    def test_x_process_time_header_present(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Process-Time", response.headers)
        # Parses as a positive float.
        value = float(response.headers["X-Process-Time"])
        self.assertGreaterEqual(value, 0.0)

    def test_buffer_records_one_sample_per_request(self):
        self.client.get("/")
        self.client.get("/")
        snap = snapshot_metrics()
        self.assertIn("GET /", snap)
        self.assertEqual(snap["GET /"]["count"], 2)
        self.assertGreaterEqual(snap["GET /"]["last_ms"], 0.0)

    def test_route_template_groups_parameterised_paths(self):
        # We don't want /events/2024 and /events/2023 to live in separate buckets.
        with patch("app.main.get_year_schedule", return_value=[]):
            self.client.get("/events/2024")
            self.client.get("/events/2023")
        snap = snapshot_metrics()
        # Should be a single bucket keyed by template.
        keys = [k for k in snap if k.startswith("GET /events/")]
        self.assertEqual(keys, ["GET /events/{year}"])
        self.assertEqual(snap["GET /events/{year}"]["count"], 2)

    def test_metrics_endpoint_returns_shape(self):
        self.client.get("/")  # seed at least one sample
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("routes", body)
        self.assertIsInstance(body["routes"], dict)
        # The /metrics call itself shows up after we read it.
        self.assertIn("GET /", body["routes"])
        for stats in body["routes"].values():
            self.assertIn("count", stats)
            self.assertIn("p50_ms", stats)
            self.assertIn("p95_ms", stats)
            self.assertIn("max_ms", stats)
            self.assertIn("last_ms", stats)

    def test_metrics_disabled_via_env(self):
        # Build a fresh app with METRICS_ENABLED=false so the middleware skips work.
        with patch.dict(os.environ, {"METRICS_ENABLED": "false"}):
            reset_metrics_for_tests()
            # We can't easily un-register middleware on the existing app; instead
            # confirm via direct module behaviour.
            from core.timing import _is_enabled

            self.assertFalse(_is_enabled())

    def test_buffer_capped_at_50(self):
        # Hammer the welcome endpoint past the cap and confirm count stays bounded.
        for _ in range(75):
            self.client.get("/")
        snap = snapshot_metrics()
        self.assertLessEqual(snap["GET /"]["count"], 50)


class TimingHelpersTests(unittest.TestCase):
    def test_percentile_empty(self):
        from core.timing import _percentile

        self.assertEqual(_percentile([], 0.5), 0.0)

    def test_percentile_single(self):
        from core.timing import _percentile

        self.assertEqual(_percentile([0.123], 0.95), 0.123)

    def test_percentile_p50_p95_monotonic(self):
        from core.timing import _percentile

        samples = [i / 100 for i in range(1, 101)]  # 0.01 .. 1.00
        p50 = _percentile(samples, 0.50)
        p95 = _percentile(samples, 0.95)
        self.assertGreater(p95, p50)


if __name__ == "__main__":
    unittest.main()
