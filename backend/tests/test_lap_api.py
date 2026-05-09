"""
Lap-list endpoint contract tests.

Patches `get_session_lap_list` so the test stays offline (no FastF1 cache hit).
The endpoint must:
- return 200 with the lap list, fastest lap number, and `status: "success"` on a healthy session,
- return 200 with `fallback=true`, `status: "error"`, and a reason string when no laps exist
  (driver not in session, session not yet run, etc).
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class LapApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.main.get_session_lap_list")
    def test_lap_endpoint_success(self, mock_laps):
        mock_laps.return_value = {
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "driver": "HAM",
            "laps": [
                {"lap_number": 1, "lap_time_seconds": 95.4, "compound": "MEDIUM", "is_pit_in": False, "is_pit_out": True},
                {"lap_number": 2, "lap_time_seconds": 92.1, "compound": "MEDIUM", "is_pit_in": False, "is_pit_out": False},
            ],
            "fastest_lap_number": 2,
            "fallback": False,
            "fallback_reason": None,
        }
        response = self.client.get("/laps/2023/Japanese Grand Prix/R/HAM")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["fallback"])
        self.assertIsNone(payload["error"])
        self.assertEqual(len(payload["laps"]), 2)
        self.assertEqual(payload["fastest_lap_number"], 2)
        self.assertEqual(payload["laps"][0]["compound"], "MEDIUM")
        self.assertTrue(payload["laps"][0]["is_pit_out"])

    @patch("app.main.get_session_lap_list")
    def test_lap_endpoint_fallback(self, mock_laps):
        mock_laps.return_value = {
            "year": 2099,
            "event": "Imaginary Grand Prix",
            "session_type": "R",
            "driver": "HAM",
            "laps": [],
            "fastest_lap_number": None,
            "fallback": True,
            "fallback_reason": "No laps found for requested driver/session.",
        }
        response = self.client.get("/laps/2099/Imaginary Grand Prix/R/HAM")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertTrue(payload["fallback"])
        self.assertEqual(payload["laps"], [])
        self.assertIsNone(payload["fastest_lap_number"])
        self.assertEqual(payload["error"], payload["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
