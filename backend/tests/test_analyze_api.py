import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests._helpers import reset_rate_limiter


class AnalyzeApiTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        self.client = TestClient(app)

    @patch("app.main.analyze_query")
    def test_analyze_endpoint_returns_agent_payload(self, mock_analyze):
        mock_analyze.return_value = {
            "intent": {"driver": "HAM", "year": 2023, "session_type": "R", "intent_type": "telemetry"},
            "telemetry_data": {"fallback": False},
            "strategy_data": None,
            "response_text": "HAM telemetry (Japanese Grand Prix 2023 R): speed avg 255.0 km/h.",
            "error": None,
            "memory": {"history_size": 1, "retention_cap": 10, "last_driver": "HAM"},
            "execution": {"termination_reason": "completed", "step_limit": 6, "duration_ms": 10.0, "duration_limit_seconds": 5.0},
            "retry": {"count": 1, "max_retries": 2, "retryable_exhausted": False, "retry_backoff_seconds": 0.1},
        }
        response = self.client.post(
            "/analyze",
            json={
                "query": "show ham telemetry",
                "driver": "HAM",
                "session_info": {"event": "Japanese Grand Prix", "year": 2023, "session_type": "R"},
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertIn("agent_response", payload)
        self.assertEqual(payload["intent"]["driver"], "HAM")
        self.assertEqual(payload["memory"]["last_driver"], "HAM")
        self.assertEqual(payload["execution"]["termination_reason"], "completed")
        self.assertEqual(payload["retry"]["count"], 1)

    @patch("app.main.analyze_query")
    def test_analyze_endpoint_returns_strategy_payload(self, mock_analyze):
        mock_analyze.return_value = {
            "intent": {"driver": "HAM", "year": 2023, "session_type": "R", "intent_type": "strategy"},
            "telemetry_data": {},
            "strategy_data": {
                "recommended_pit_window_laps": [8, 14],
                "undercut_risk": "medium",
                "overcut_risk": "low",
                "confidence_band": "medium",
                "assumptions": ["Current gap to rival considered: 1.2s."],
                "rationale": ["Predicted degradation rate: 0.310s/lap."],
                "fallback": False,
                "fallback_reason": None,
            },
            "response_text": "Baseline strategy recommendation for HAM: consider pit window laps 8-14.",
            "error": None,
            "memory": {"history_size": 1, "retention_cap": 10, "last_driver": "HAM"},
            "execution": {"termination_reason": "completed", "step_limit": 6, "duration_ms": 10.0, "duration_limit_seconds": 5.0},
            "retry": {"count": 0, "max_retries": 2, "retryable_exhausted": False, "retry_backoff_seconds": 0.1},
        }
        response = self.client.post(
            "/analyze",
            json={
                "query": "should ham pit soon",
                "driver": "HAM",
                "session_info": {"event": "Japanese Grand Prix", "year": 2023, "session_type": "R"},
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["intent"]["intent_type"], "strategy")
        self.assertEqual(payload["strategy_data"]["confidence_band"], "medium")
        self.assertEqual(payload["strategy_data"]["recommended_pit_window_laps"], [8, 14])

    @patch("app.main.analyze_query")
    def test_analyze_endpoint_forwards_session_info_and_driver_to_agent(self, mock_analyze):
        mock_analyze.return_value = {
            "intent": {"driver": "VER", "year": 2024, "session_type": "Q", "intent_type": "telemetry"},
            "telemetry_data": {"fallback": False},
            "strategy_data": None,
            "response_text": "ok",
            "error": None,
            "memory": {"history_size": 0, "retention_cap": 10, "last_driver": "VER"},
            "execution": {"termination_reason": "completed", "step_limit": 6, "duration_ms": 1.0, "duration_limit_seconds": 5.0},
            "retry": {"count": 0, "max_retries": 2, "retryable_exhausted": False, "retry_backoff_seconds": 0.1},
        }
        response = self.client.post(
            "/analyze",
            json={
                "query": "show me the data",
                "driver": "VER",
                "session_info": {"event": "Monaco Grand Prix", "year": 2024, "session_type": "Q"},
            },
        )
        self.assertEqual(response.status_code, 200)
        mock_analyze.assert_called_once()
        args, kwargs = mock_analyze.call_args
        self.assertEqual(args[0], "show me the data")
        self.assertEqual(kwargs["driver_override"], "VER")
        self.assertEqual(
            kwargs["session_override"],
            {"event": "Monaco Grand Prix", "year": 2024, "session_type": "Q"},
        )

    def test_openapi_exposes_docs_metadata_for_core_routes(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["info"]["title"], "Apex-Intelligence: Virtual Race Engineer API")
        self.assertEqual(payload["info"]["version"], "0.1.0")
        self.assertIn("/analyze", payload["paths"])
        self.assertIn("/telemetry", payload["paths"])
        analyze_post = payload["paths"]["/analyze"]["post"]
        self.assertEqual(analyze_post["summary"], "Analyze a telemetry or strategy question")
        self.assertEqual(analyze_post["tags"], ["analysis"])
        telemetry_post = payload["paths"]["/telemetry"]["post"]
        self.assertEqual(telemetry_post["tags"], ["telemetry"])
        self.assertIn("AnalyzeRequest", payload["components"]["schemas"])


if __name__ == "__main__":
    unittest.main()
