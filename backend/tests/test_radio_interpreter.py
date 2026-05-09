"""Tests for the radio interpreter agent and `/radio/analyze` endpoint.

Strategy mirrors `test_llm_rationale.py` — patch the LLM wrapper directly
so neither runner reaches the real Gemini SDK. Five fixture transcripts
exercise the main classification categories from the issue's acceptance
criteria; additional tests cover the fail-closed validation branches.
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents import radio_interpreter
from app.main import app
from tests._helpers import reset_rate_limiter


FIXTURE_TRANSCRIPTS = [
    {
        "name": "tyre",
        "transcript": "Box box box, the rears are completely gone, no grip out of the chicane.",
        "expected_classification": "tyre_issue",
        "expected_severity": "high",
        "expected_phrase": "the rears are completely gone",
    },
    {
        "name": "brake",
        "transcript": "I've got a vibration on the brakes into turn 1, getting worse every lap.",
        "expected_classification": "brake_issue",
        "expected_severity": "medium",
        "expected_phrase": "vibration on the brakes",
    },
    {
        "name": "engine",
        "transcript": "Power loss on the straight, the engine is cutting out at high revs.",
        "expected_classification": "engine_issue",
        "expected_severity": "high",
        "expected_phrase": "engine is cutting out",
    },
    {
        "name": "traffic",
        "transcript": "Backmarker on the racing line into 130R, I lost half a second there.",
        "expected_classification": "traffic",
        "expected_severity": "low",
        "expected_phrase": "Backmarker on the racing line",
    },
    {
        "name": "weather",
        "transcript": "Rain spotting at turn 7, the front-left is starting to slide.",
        "expected_classification": "weather",
        "expected_severity": "medium",
        "expected_phrase": "Rain spotting at turn 7",
    },
]


class RadioInterpreterUnitTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()

    def test_each_fixture_transcript_classifies_into_expected_category(self):
        for fixture in FIXTURE_TRANSCRIPTS:
            with self.subTest(category=fixture["name"]):
                fake_response = {
                    "classification": fixture["expected_classification"],
                    "severity": fixture["expected_severity"],
                    "trigger_phrase": fixture["expected_phrase"],
                }
                with patch.object(radio_interpreter, "generate_structured", return_value=fake_response):
                    result = radio_interpreter.interpret_radio(fixture["transcript"], driver="HAM")
                self.assertFalse(result["fallback"])
                self.assertEqual(result["classification"], fixture["expected_classification"])
                self.assertEqual(result["severity"], fixture["expected_severity"])
                self.assertEqual(result["trigger_phrase"], fixture["expected_phrase"])

    def test_strategy_request_classification(self):
        fake_response = {
            "classification": "strategy_request",
            "severity": "low",
            "trigger_phrase": "what's the plan for the next stint",
        }
        with patch.object(radio_interpreter, "generate_structured", return_value=fake_response):
            result = radio_interpreter.interpret_radio("Mate, what's the plan for the next stint?")
        self.assertFalse(result["fallback"])
        self.assertEqual(result["classification"], "strategy_request")

    def test_none_classification_allows_empty_trigger_phrase(self):
        fake_response = {
            "classification": "none",
            "severity": "low",
            "trigger_phrase": "",
        }
        with patch.object(radio_interpreter, "generate_structured", return_value=fake_response):
            result = radio_interpreter.interpret_radio("Copy, thanks for the info.")
        self.assertFalse(result["fallback"])
        self.assertEqual(result["classification"], "none")

    def test_returns_fallback_when_llm_unavailable(self):
        with patch.object(radio_interpreter, "generate_structured", return_value=None):
            result = radio_interpreter.interpret_radio("Box box, tyres gone.")
        self.assertTrue(result["fallback"])
        self.assertEqual(result["classification"], "none")
        self.assertEqual(result["severity"], "low")
        self.assertEqual(result["trigger_phrase"], "")
        self.assertIsNotNone(result["fallback_reason"])

    def test_returns_fallback_when_classification_outside_enum(self):
        bad_response = {
            "classification": "alien_invasion",
            "severity": "high",
            "trigger_phrase": "they're here",
        }
        with patch.object(radio_interpreter, "generate_structured", return_value=bad_response):
            result = radio_interpreter.interpret_radio("Strange lights above the track.")
        self.assertTrue(result["fallback"])
        self.assertEqual(result["classification"], "none")

    def test_returns_fallback_when_required_key_missing(self):
        bad_response = {"classification": "tyre_issue"}  # no severity, no trigger_phrase
        with patch.object(radio_interpreter, "generate_structured", return_value=bad_response):
            result = radio_interpreter.interpret_radio("Box box.")
        self.assertTrue(result["fallback"])

    def test_returns_fallback_when_trigger_phrase_empty_for_non_none(self):
        bad_response = {
            "classification": "tyre_issue",
            "severity": "high",
            "trigger_phrase": "   ",
        }
        with patch.object(radio_interpreter, "generate_structured", return_value=bad_response):
            result = radio_interpreter.interpret_radio("Tyres gone.")
        self.assertTrue(result["fallback"])

    def test_returns_fallback_when_severity_outside_enum(self):
        bad_response = {
            "classification": "tyre_issue",
            "severity": "catastrophic",
            "trigger_phrase": "tyres gone",
        }
        with patch.object(radio_interpreter, "generate_structured", return_value=bad_response):
            result = radio_interpreter.interpret_radio("Tyres gone.")
        self.assertTrue(result["fallback"])


class RadioApiTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        self.client = TestClient(app)

    @patch("app.main.interpret_radio")
    def test_radio_endpoint_returns_classification(self, mock_interpret):
        mock_interpret.return_value = {
            "classification": "tyre_issue",
            "severity": "high",
            "trigger_phrase": "rears are gone",
            "fallback": False,
            "fallback_reason": None,
        }
        response = self.client.post(
            "/radio/analyze",
            json={"transcript": "Box box, the rears are gone.", "driver": "HAM"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["classification"], "tyre_issue")
        self.assertEqual(payload["severity"], "high")
        self.assertEqual(payload["trigger_phrase"], "rears are gone")
        self.assertFalse(payload["fallback"])
        mock_interpret.assert_called_once_with(
            transcript="Box box, the rears are gone.",
            driver="HAM",
        )

    @patch("app.main.interpret_radio")
    def test_radio_endpoint_returns_fallback_envelope(self, mock_interpret):
        mock_interpret.return_value = {
            "classification": "none",
            "severity": "low",
            "trigger_phrase": "",
            "fallback": True,
            "fallback_reason": "LLM unavailable or returned no output",
        }
        response = self.client.post(
            "/radio/analyze",
            json={"transcript": "Some transcript here."},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertTrue(payload["fallback"])
        self.assertEqual(payload["classification"], "none")
        self.assertEqual(payload["fallback_reason"], "LLM unavailable or returned no output")

    def test_radio_endpoint_rejects_too_short_transcript(self):
        response = self.client.post("/radio/analyze", json={"transcript": "ok"})
        self.assertEqual(response.status_code, 422)

    def test_radio_endpoint_rejects_invalid_driver_length(self):
        response = self.client.post(
            "/radio/analyze",
            json={"transcript": "Box box.", "driver": "HAMILTON"},
        )
        self.assertEqual(response.status_code, 422)

    def test_openapi_exposes_radio_endpoint(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("/radio/analyze", payload["paths"])
        radio_post = payload["paths"]["/radio/analyze"]["post"]
        self.assertEqual(radio_post["tags"], ["analysis"])
        self.assertEqual(radio_post["summary"], "Classify a team-radio transcript")
        self.assertIn("RadioRequest", payload["components"]["schemas"])
        self.assertIn("RadioResponse", payload["components"]["schemas"])


if __name__ == "__main__":
    unittest.main()
