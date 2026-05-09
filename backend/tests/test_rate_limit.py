"""
Rate-limit envelope tests for /analyze, /telemetry, /laps.

Burst above the configured threshold and confirm the structured 429 response
shape (status=error, error.code=rate_limited, retry_after_seconds, Retry-After
header). Limits configured in app.main:
- /analyze:   3 / 10 seconds
- /telemetry: 30 / 10 seconds
- /laps:      30 / 10 seconds
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests._helpers import reset_rate_limiter


def _analyze_payload():
    return {
        "intent": {"driver": "HAM", "year": 2023, "session_type": "R", "intent_type": "telemetry"},
        "telemetry_data": {"fallback": False},
        "strategy_data": None,
        "response_text": "ok",
        "error": None,
        "memory": {"history_size": 0, "retention_cap": 10, "last_driver": "HAM"},
        "execution": {"termination_reason": "completed", "step_limit": 6, "duration_ms": 1.0, "duration_limit_seconds": 5.0},
        "retry": {"count": 0, "max_retries": 2, "retryable_exhausted": False, "retry_backoff_seconds": 0.1},
    }


def _lap_list_payload():
    return {
        "year": 2023,
        "event": "Japanese Grand Prix",
        "session_type": "R",
        "driver": "HAM",
        "laps": [],
        "fastest_lap_number": None,
        "fallback": False,
        "fallback_reason": None,
    }


def _telemetry_payload():
    return {
        "driver": "HAM",
        "year": 2023,
        "event": "Japanese Grand Prix",
        "session_type": "R",
        "sample_points": 0,
        "speed": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "km/h", "series": []},
        "gear": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "gear", "series": []},
        "rpm": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "rpm", "series": []},
        "fallback": False,
        "fallback_reason": None,
        "lap_number": 1,
        "lap_duration_s": None,
        "sector_boundaries_s": [],
    }


def _assert_rate_limited(case, response, expected_window: int):
    case.assertEqual(response.status_code, 429)
    body = response.json()
    case.assertEqual(body["status"], "error")
    case.assertEqual(body["error"]["code"], "rate_limited")
    case.assertEqual(body["error"]["retry_after_seconds"], expected_window)
    case.assertIn("Retry in", body["error"]["message"])
    case.assertEqual(response.headers.get("Retry-After"), str(expected_window))


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        self.client = TestClient(app)

    @patch("app.main.analyze_query")
    def test_analyze_returns_429_after_burst(self, mock_analyze):
        mock_analyze.return_value = _analyze_payload()
        body = {
            "query": "show ham telemetry",
            "driver": "HAM",
            "session_info": {"event": "Japanese Grand Prix", "year": 2023, "session_type": "R"},
        }
        # /analyze limit is 3/10s — first 3 succeed, the 4th must be rate-limited.
        for _ in range(3):
            ok = self.client.post("/analyze", json=body)
            self.assertEqual(ok.status_code, 200)

        limited = self.client.post("/analyze", json=body)
        _assert_rate_limited(self, limited, expected_window=10)

    @patch("app.main.get_session_lap_list")
    def test_laps_returns_429_after_burst(self, mock_laps):
        mock_laps.return_value = _lap_list_payload()
        # /laps limit is 30/10s — fire 30 successful requests, the 31st is limited.
        for _ in range(30):
            ok = self.client.get("/laps/2023/Japanese Grand Prix/R/HAM")
            self.assertEqual(ok.status_code, 200)

        limited = self.client.get("/laps/2023/Japanese Grand Prix/R/HAM")
        _assert_rate_limited(self, limited, expected_window=10)

    @patch("app.main.get_session_telemetry_summary")
    def test_telemetry_returns_429_after_burst(self, mock_tel):
        mock_tel.return_value = _telemetry_payload()
        body = {
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "driver": "HAM",
            "lap_number": 1,
        }
        # /telemetry limit is 30/10s — fire 30 successful requests, the 31st is limited.
        for _ in range(30):
            ok = self.client.post("/telemetry", json=body)
            self.assertEqual(ok.status_code, 200)

        limited = self.client.post("/telemetry", json=body)
        _assert_rate_limited(self, limited, expected_window=10)


if __name__ == "__main__":
    unittest.main()
