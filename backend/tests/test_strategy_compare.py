"""Tests for the /strategy/compare scenario what-if endpoint (#202)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests._helpers import reset_rate_limiter
from tools.knowledge_retriever import reset_index_cache
from tools.strategy_compare import compare_scenarios


def _helper_envelope(
    *,
    pit_window: tuple[int, int] = (12, 18),
    expected_gain: float | None = 1.4,
    gap: float = 1.5,
) -> dict:
    return {
        "driver": "HAM",
        "year": 2023,
        "event": "Japanese Grand Prix",
        "session_type": "R",
        "fallback": False,
        "fallback_reason": None,
        "strategy": {
            "recommended_pit_window_laps": list(pit_window),
            "undercut_risk": "high",
            "overcut_risk": "low",
            "confidence_band": "medium",
            "assumptions": [],
            "rationale": [],
            "current_gap_seconds": gap,
            "gap_source": "explicit",
            "competitor_ahead": "VER",
            "competitor_position_relative": "ahead",
            "gap_sampled_at_lap": 12,
            "pit_loss_seconds": 22.0,
            "undercut_break_even_laps": 3,
            "expected_gain_seconds": expected_gain,
        },
        "tyre_prediction": {},
    }


class CompareScenariosOrchestratorTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        reset_index_cache()

    @patch("tools.strategy_compare.strategy_analyzer")
    def test_distinct_gap_overrides_yield_distinct_outcomes(self, mock_helper):
        # The orchestrator must thread each scenario's gap_override through to
        # the helper and surface different outcomes for them. Without this
        # propagation the whole compare endpoint is decorative.
        def _branched(*_args, current_gap_seconds: float | None = None, **_kw):
            if current_gap_seconds == 0.8:
                return _helper_envelope(expected_gain=2.4, gap=0.8)
            return _helper_envelope(expected_gain=0.6, gap=2.5)

        mock_helper.side_effect = _branched

        outcomes = compare_scenarios(
            year=2023,
            event="Japanese Grand Prix",
            session_type="R",
            driver="HAM",
            target_driver="VER",
            scenarios=[
                {"label": "Undercut now", "gap_override_seconds": 0.8, "target_driver": None},
                {"label": "Hold + 3 laps", "gap_override_seconds": 2.5, "target_driver": None},
            ],
        )
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(outcomes[0]["expected_gain_seconds"], 2.4)
        self.assertEqual(outcomes[1]["expected_gain_seconds"], 0.6)
        self.assertEqual(outcomes[0]["current_gap_seconds"], 0.8)
        self.assertEqual(outcomes[1]["current_gap_seconds"], 2.5)

    @patch("tools.strategy_compare.strategy_analyzer")
    def test_distinct_labels_yield_distinct_top_citation(self, mock_helper):
        # The corpus has both `strategy-undercut` and `strategy-overcut`
        # entries; a label biased toward each should drag a different
        # snippet to the top of the BM25 ranking.
        mock_helper.return_value = _helper_envelope()

        outcomes = compare_scenarios(
            year=2023,
            event="Japanese Grand Prix",
            session_type="R",
            driver="HAM",
            target_driver="VER",
            scenarios=[
                {"label": "Undercut", "gap_override_seconds": None, "target_driver": None},
                {"label": "Overcut", "gap_override_seconds": None, "target_driver": None},
            ],
        )
        self.assertEqual(len(outcomes), 2)
        self.assertTrue(outcomes[0]["citations"], "expected citations for undercut scenario")
        self.assertTrue(outcomes[1]["citations"], "expected citations for overcut scenario")
        self.assertEqual(outcomes[0]["citations"][0]["id"], "strategy-undercut")
        self.assertEqual(outcomes[1]["citations"][0]["id"], "strategy-overcut")

    @patch("tools.strategy_compare.strategy_analyzer")
    def test_helper_exception_in_one_scenario_does_not_break_others(self, mock_helper):
        # Per-scenario fail-closed: a runtime error in slot 0 must not
        # cascade into slot 1.
        def _branched(*_args, current_gap_seconds: float | None = None, **_kw):
            if current_gap_seconds == 0.5:
                raise RuntimeError("FastF1 boom")
            return _helper_envelope(expected_gain=1.1, gap=2.5)

        mock_helper.side_effect = _branched

        outcomes = compare_scenarios(
            year=2023,
            event="Japanese Grand Prix",
            session_type="R",
            driver="HAM",
            target_driver="VER",
            scenarios=[
                {"label": "Aggressive undercut", "gap_override_seconds": 0.5, "target_driver": None},
                {"label": "Steady hold", "gap_override_seconds": 2.5, "target_driver": None},
            ],
        )
        self.assertEqual(len(outcomes), 2)
        self.assertTrue(outcomes[0]["fallback"])
        self.assertIn("FastF1 boom", outcomes[0]["fallback_reason"])
        self.assertFalse(outcomes[1]["fallback"])
        self.assertEqual(outcomes[1]["expected_gain_seconds"], 1.1)

    @patch("tools.strategy_compare.strategy_analyzer")
    def test_helper_fallback_envelope_propagates_to_outcome(self, mock_helper):
        mock_helper.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "fallback": True,
            "fallback_reason": "Tyre features unavailable",
            "strategy": {
                "recommended_pit_window_laps": [0, 0],
                "undercut_risk": "unknown",
                "overcut_risk": "unknown",
                "confidence_band": "low",
                "assumptions": [],
                "rationale": [],
            },
        }

        outcomes = compare_scenarios(
            year=2023,
            event="Japanese Grand Prix",
            session_type="R",
            driver="HAM",
            target_driver="VER",
            scenarios=[
                {"label": "Undercut", "gap_override_seconds": None, "target_driver": None},
            ],
        )
        self.assertEqual(len(outcomes), 1)
        self.assertTrue(outcomes[0]["fallback"])
        self.assertIn("Tyre features unavailable", outcomes[0]["fallback_reason"])
        self.assertEqual(outcomes[0]["citations"], [])


class StrategyCompareEndpointTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        reset_index_cache()
        self.client = TestClient(app)

    @patch("tools.strategy_compare.strategy_analyzer")
    def test_endpoint_returns_per_scenario_outcomes(self, mock_helper):
        mock_helper.return_value = _helper_envelope()
        res = self.client.post(
            "/strategy/compare",
            json={
                "year": 2023,
                "event": "Japanese Grand Prix",
                "session_type": "R",
                "driver": "HAM",
                "target_driver": "VER",
                "scenarios": [
                    {"label": "Undercut", "gap_override_seconds": 0.8},
                    {"label": "Overcut", "gap_override_seconds": 2.5},
                ],
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(len(body["scenarios"]), 2)
        labels = [s["label"] for s in body["scenarios"]]
        self.assertEqual(labels, ["Undercut", "Overcut"])

    def test_endpoint_rejects_too_many_scenarios(self):
        payload = {
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "driver": "HAM",
            "scenarios": [
                {"label": f"Slot {i}"} for i in range(4)
            ],
        }
        res = self.client.post("/strategy/compare", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_endpoint_rejects_empty_scenarios(self):
        payload = {
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "driver": "HAM",
            "scenarios": [],
        }
        res = self.client.post("/strategy/compare", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_endpoint_openapi_registration(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/strategy/compare", schema["paths"])
        op = schema["paths"]["/strategy/compare"]["post"]
        self.assertIn("analysis", op["tags"])


if __name__ == "__main__":
    unittest.main()
