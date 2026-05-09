"""
Roster endpoint contract tests.

Patches `get_event_drivers` so the test stays offline (no FastF1 cache hit).
The endpoint must:
- return 200 with the driver list and `status: "success"` on a healthy roster,
- return 200 with `fallback=true`, `status: "error"`, and a reason string when
  the helper signals no roster data (e.g. event not yet raced).
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class RosterApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.main.get_event_drivers")
    def test_roster_endpoint_success(self, mock_drivers):
        mock_drivers.return_value = {
            "year": 2023,
            "event": "Japanese Grand Prix",
            "drivers": ["VER", "PER", "HAM", "NOR"],
            "source_session": "R",
            "fallback": False,
            "fallback_reason": None,
        }
        response = self.client.get("/events/2023/Japanese Grand Prix/drivers")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["fallback"])
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["drivers"], ["VER", "PER", "HAM", "NOR"])
        self.assertEqual(payload["source_session"], "R")

    @patch("app.main.get_event_drivers")
    def test_roster_endpoint_fallback(self, mock_drivers):
        mock_drivers.return_value = {
            "year": 2099,
            "event": "Imaginary Grand Prix",
            "drivers": [],
            "source_session": None,
            "fallback": True,
            "fallback_reason": "Event has no race or qualifying sessions yet.",
        }
        response = self.client.get("/events/2099/Imaginary Grand Prix/drivers")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertTrue(payload["fallback"])
        self.assertEqual(payload["drivers"], [])
        self.assertIn("Imaginary", payload["event"])
        self.assertIn("no race", payload["fallback_reason"])
        self.assertEqual(payload["error"], payload["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
