import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests._helpers import reset_rate_limiter


class TelemetryApiTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        self.client = TestClient(app)

    @patch("app.main.get_session_telemetry_summary")
    def test_telemetry_endpoint_success_contract(self, mock_summary):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 3,
            "speed": {"min": 250.0, "max": 260.0, "avg": 255.0, "unit": "km/h"},
            "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
            "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": False,
            "fallback_reason": None,
        }
        response = self.client.post(
            "/telemetry",
            json={"year": 2023, "event": "Japanese Grand Prix", "session_type": "R", "driver": "HAM"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["data"]["speed"]["unit"], "km/h")
        self.assertEqual(payload["data"]["gear"]["unit"], "gear")
        self.assertEqual(payload["data"]["rpm"]["unit"], "rpm")

    @patch("app.main.get_session_telemetry_summary")
    def test_telemetry_endpoint_fallback_contract(self, mock_summary):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 0,
            "speed": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "km/h"},
            "gear": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "gear"},
            "rpm": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": True,
            "fallback_reason": "No laps found",
        }
        response = self.client.post(
            "/telemetry",
            json={"year": 2023, "event": "Japanese Grand Prix", "session_type": "R", "driver": "HAM"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "TELEMETRY_UNAVAILABLE")
        self.assertTrue(payload["data"]["fallback"])


if __name__ == "__main__":
    unittest.main()
