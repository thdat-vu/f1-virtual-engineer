"""End-to-end tests for the format_response_node LLM/template branching.

These tests monkeypatch ``agents.race_engineer.generate_rationale`` directly
so we cover both branches without touching the real Gemini SDK. Note: the
autouse pytest fixture in conftest.py forces the template path by default;
LLM-path tests re-patch with their own return value.
"""

import unittest
from unittest.mock import MagicMock, patch

from agents import race_engineer
from agents.race_engineer import format_response_node, reset_memory_store
from tests._helpers import force_template_rationale


def _telemetry_state(error: str | None = None) -> dict:
    return {
        "query": "show ham telemetry",
        "intent": {"driver": "HAM", "year": 2023, "session_type": "R", "intent_type": "telemetry", "event": "Japanese Grand Prix"},
        "telemetry_data": {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "speed": {"min": 100.0, "max": 300.0, "avg": 200.0, "unit": "km/h"},
            "gear": {"min": 1.0, "max": 8.0, "avg": 5.5, "unit": "gear"},
            "rpm": {"min": 8000.0, "max": 12000.0, "avg": 10000.0, "unit": "rpm"},
            "fallback": False,
        },
        "strategy_data": {},
        "response_text": "",
        "error": error,
        "memory": {},
        "retry_count": 0,
        "retry_metadata": {},
        "overrides": {},
        "rationale_source": "template",
    }


class FormatResponseLLMBranchTests(unittest.TestCase):
    def setUp(self):
        reset_memory_store()
        force_template_rationale()

    def test_format_response_uses_llm_when_available(self):
        with patch.object(race_engineer, "generate_rationale", return_value="LLM-generated rationale text"):
            result = format_response_node(_telemetry_state())
        self.assertEqual(result["response_text"], "LLM-generated rationale text")
        self.assertEqual(result["rationale_source"], "llm")

    def test_format_response_falls_back_to_template_when_llm_returns_none(self):
        with patch.object(race_engineer, "generate_rationale", return_value=None):
            result = format_response_node(_telemetry_state())
        self.assertIn("HAM telemetry (Japanese Grand Prix 2023 R)", result["response_text"])
        self.assertIn("speed avg 200.0 km/h", result["response_text"])
        self.assertEqual(result["rationale_source"], "template")

    def test_format_response_falls_back_when_llm_returns_empty_string(self):
        with patch.object(race_engineer, "generate_rationale", return_value=""):
            result = format_response_node(_telemetry_state())
        self.assertIn("HAM telemetry", result["response_text"])
        self.assertEqual(result["rationale_source"], "template")

    def test_llm_path_skipped_for_error_branch(self):
        spy = MagicMock(return_value="should never be returned")
        with patch.object(race_engineer, "generate_rationale", spy):
            result = format_response_node(_telemetry_state(error="Boom"))
        spy.assert_not_called()
        self.assertEqual(result["response_text"], "Boom")
        self.assertEqual(result["rationale_source"], "template")

    def test_llm_path_skipped_for_telemetry_fallback_branch(self):
        spy = MagicMock(return_value="should never be returned")
        state = _telemetry_state()
        state["telemetry_data"]["fallback"] = True
        state["telemetry_data"]["fallback_reason"] = "no laps"
        with patch.object(race_engineer, "generate_rationale", spy):
            result = format_response_node(state)
        spy.assert_not_called()
        self.assertEqual(result["response_text"], "Telemetry unavailable: no laps")
        self.assertEqual(result["rationale_source"], "template")


if __name__ == "__main__":
    unittest.main()
