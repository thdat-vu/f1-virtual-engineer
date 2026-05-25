"""Tests for tools.tyre_helper.compute_tyre_decay (#167)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests._helpers import reset_rate_limiter
from tools import tyre_helper


def _prediction_envelope(*, decay: float, drop_window: list[int], confidence: str = "medium") -> dict:
    """Shape returned by tools.strategy_helper.predict_tyre_wear."""
    return {
        "driver": "HAM",
        "year": 2024,
        "event": "Italian Grand Prix",
        "session_type": "R",
        "fallback": False,
        "fallback_reason": None,
        "prediction": {
            "degradation_rate_seconds_per_lap": decay,
            "confidence_band": confidence,
            "expected_performance_drop_window_laps": drop_window,
            "reasons": ["test"],
        },
    }


def _roster(*, laps: list[dict]) -> dict:
    return {
        "year": 2024,
        "event": "Italian Grand Prix",
        "session_type": "R",
        "driver": "HAM",
        "laps": laps,
        "fastest_lap_number": None,
        "fallback": False,
        "fallback_reason": None,
    }


class TyreHelperTests(unittest.TestCase):
    def test_returns_full_snapshot_on_happy_path(self):
        # Eight laps in the current stint after a pit-in on lap 12. The
        # cliff window starts at offset 8, decay is moderate, so the
        # estimator should pin the cliff at the start of the window.
        roster = _roster(laps=[
            {"lap_number": i, "lap_time_seconds": 80 + i * 0.05, "compound": "HARD",
             "is_pit_in": i == 12, "is_pit_out": i == 13}
            for i in range(1, 21)
        ])
        with patch.object(tyre_helper, "predict_tyre_wear", return_value=_prediction_envelope(
            decay=0.18, drop_window=[8, 14], confidence="high",
        )), patch.object(tyre_helper, "get_session_lap_list", return_value=roster):
            result = tyre_helper.compute_tyre_decay(2024, "Italian Grand Prix", "R", "ham")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["driver"], "HAM")
        self.assertEqual(result["compound"], "HARD")
        self.assertEqual(result["stint_laps"], 8)  # laps 13..20 → 8 (pit-in at 12 breaks)
        self.assertAlmostEqual(result["decay_seconds_per_lap"], 0.18)
        self.assertEqual(result["confidence_band"], "high")
        self.assertEqual(result["cliff_lap_estimate"], 8)
        # #185: snapshot lap is the last lap in the loaded roster.
        self.assertEqual(result["last_lap_number"], 20)
        # #223: actual pit-in laps surfaced for historical grounding.
        self.assertEqual(result["actual_pit_laps"], [12])

    def test_steep_decay_pulls_cliff_earlier(self):
        # Same window but decay > 0.45 — estimator should subtract 2.
        roster = _roster(laps=[
            {"lap_number": i, "lap_time_seconds": 80 + i * 0.5, "compound": "SOFT",
             "is_pit_in": False, "is_pit_out": i == 1}
            for i in range(1, 6)
        ])
        with patch.object(tyre_helper, "predict_tyre_wear", return_value=_prediction_envelope(
            decay=0.55, drop_window=[8, 14],
        )), patch.object(tyre_helper, "get_session_lap_list", return_value=roster):
            result = tyre_helper.compute_tyre_decay(2024, "Italian Grand Prix", "R", "HAM")

        self.assertEqual(result["cliff_lap_estimate"], 6)  # 8 - 2

    def test_stint_already_past_cliff_returns_now(self):
        # 10 laps run, drop window started at offset 8 → cliff = "now".
        roster = _roster(laps=[
            {"lap_number": i, "lap_time_seconds": 80 + i * 0.1, "compound": "MEDIUM",
             "is_pit_in": False, "is_pit_out": i == 1}
            for i in range(1, 11)
        ])
        with patch.object(tyre_helper, "predict_tyre_wear", return_value=_prediction_envelope(
            decay=0.30, drop_window=[8, 14],
        )), patch.object(tyre_helper, "get_session_lap_list", return_value=roster):
            result = tyre_helper.compute_tyre_decay(2024, "Italian Grand Prix", "R", "HAM")

        self.assertEqual(result["cliff_lap_estimate"], 10)
        self.assertEqual(result["stint_laps"], 10)

    def test_prediction_fallback_returns_empty_envelope(self):
        with patch.object(tyre_helper, "predict_tyre_wear", return_value={
            "driver": "HAM",
            "year": 2024,
            "event": "Italian Grand Prix",
            "session_type": "R",
            "fallback": True,
            "fallback_reason": "No laps found",
            "prediction": {},
        }):
            result = tyre_helper.compute_tyre_decay(2024, "Italian Grand Prix", "R", "HAM")

        self.assertTrue(result["fallback"])
        self.assertEqual(result["fallback_reason"], "No laps found")
        self.assertIsNone(result["compound"])
        self.assertEqual(result["stint_laps"], 0)
        self.assertEqual(result["decay_seconds_per_lap"], 0.0)
        self.assertIsNone(result["cliff_lap_estimate"])
        self.assertEqual(result["confidence_band"], "low")
        self.assertIsNone(result["last_lap_number"])
        self.assertEqual(result["actual_pit_laps"], [])

    def test_multi_stop_race_returns_all_pit_laps(self):
        # Three-stint race: pits on lap 16 and lap 34. Snapshot at lap 58
        # (race finish). Mirrors the AU GP LEC scenario from #223 where
        # the card said "pit now" for a finished race.
        roster = _roster(laps=[
            {"lap_number": i, "lap_time_seconds": 85.0, "compound": "HARD",
             "is_pit_in": i in (16, 34), "is_pit_out": i in (17, 35)}
            for i in range(1, 59)
        ])
        with patch.object(tyre_helper, "predict_tyre_wear", return_value=_prediction_envelope(
            decay=0.20, drop_window=[8, 14],
        )), patch.object(tyre_helper, "get_session_lap_list", return_value=roster):
            result = tyre_helper.compute_tyre_decay(2024, "Italian Grand Prix", "R", "HAM")

        self.assertEqual(result["actual_pit_laps"], [16, 34])
        self.assertEqual(result["last_lap_number"], 58)

    def test_roster_fallback_keeps_prediction_data(self):
        # Lap roster blowing up must not blank the whole card — we still
        # have a valid prediction, just no compound/stint_laps to show.
        with patch.object(tyre_helper, "predict_tyre_wear", return_value=_prediction_envelope(
            decay=0.20, drop_window=[8, 14],
        )), patch.object(tyre_helper, "get_session_lap_list", side_effect=RuntimeError("FastF1 down")):
            result = tyre_helper.compute_tyre_decay(2024, "Italian Grand Prix", "R", "HAM")

        self.assertFalse(result["fallback"])
        self.assertIsNone(result["compound"])
        self.assertEqual(result["stint_laps"], 0)
        self.assertAlmostEqual(result["decay_seconds_per_lap"], 0.20)
        # cliff estimate shouldn't fire when stint_laps is 0
        self.assertEqual(result["cliff_lap_estimate"], 8)


class TyreAnalyzeApiTests(unittest.TestCase):
    """Smoke tests for POST /tyre/analyze."""

    def setUp(self) -> None:
        reset_rate_limiter()
        self.client = TestClient(app)

    def test_endpoint_returns_success_envelope(self):
        snapshot = {
            "driver": "HAM", "year": 2024, "event": "Italian Grand Prix",
            "session_type": "R", "fallback": False, "fallback_reason": None,
            "compound": "HARD", "stint_laps": 8, "decay_seconds_per_lap": 0.18,
            "cliff_lap_estimate": 8, "confidence_band": "high",
        }
        with patch("app.main.compute_tyre_decay", return_value=snapshot):
            response = self.client.post(
                "/tyre/analyze",
                json={"year": 2024, "event": "Italian Grand Prix",
                      "session_type": "R", "driver": "HAM"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["compound"], "HARD")
        self.assertEqual(body["cliff_lap_estimate"], 8)

    def test_endpoint_marks_fallback_as_error(self):
        snapshot = {
            "driver": "HAM", "year": 2024, "event": "Italian Grand Prix",
            "session_type": "R", "fallback": True,
            "fallback_reason": "No laps found",
            "compound": None, "stint_laps": 0, "decay_seconds_per_lap": 0.0,
            "cliff_lap_estimate": None, "confidence_band": "low",
        }
        with patch("app.main.compute_tyre_decay", return_value=snapshot):
            response = self.client.post(
                "/tyre/analyze",
                json={"year": 2024, "event": "Italian Grand Prix",
                      "session_type": "R", "driver": "HAM"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertTrue(body["fallback"])


if __name__ == "__main__":
    unittest.main()
