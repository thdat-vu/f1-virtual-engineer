import unittest
from unittest.mock import patch

from tools.strategy_helper import predict_tyre_wear, strategy_analyzer


class StrategyHelperTests(unittest.TestCase):
    @patch("tools.strategy_helper.extract_tyre_wear_features")
    def test_predict_tyre_wear_success(self, mock_extract):
        mock_extract.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "features": {
                "lap_count": 20,
                "stint_count": 2,
                "lap_time_decay_seconds_per_lap": 0.22,
                "stint_progress_ratio": 0.6,
                "avg_track_temp_c": 34.0,
                "track_temp_trend_c_per_lap": 0.2,
                "temperature_missing": False,
            },
        }
        result = predict_tyre_wear(2023, "Japanese Grand Prix", "R", "HAM")

        self.assertFalse(result["fallback"])
        self.assertGreaterEqual(result["prediction"]["degradation_rate_seconds_per_lap"], 0.0)
        self.assertIn(result["prediction"]["confidence_band"], {"high", "medium", "low"})
        self.assertEqual(len(result["prediction"]["expected_performance_drop_window_laps"]), 2)

    @patch("tools.strategy_helper.extract_tyre_wear_features")
    def test_predict_tyre_wear_handles_fallback(self, mock_extract):
        mock_extract.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "fallback": True,
            "fallback_reason": "No laps found",
            "features": {
                "lap_count": 0,
                "stint_count": 0,
                "lap_time_decay_seconds_per_lap": 0.0,
                "stint_progress_ratio": 0.0,
                "avg_track_temp_c": None,
                "track_temp_trend_c_per_lap": None,
                "temperature_missing": True,
            },
        }
        result = predict_tyre_wear(2023, "Japanese Grand Prix", "R", "HAM")

        self.assertTrue(result["fallback"])
        self.assertEqual(result["prediction"]["confidence_band"], "low")

    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_strategy_analyzer_success(self, mock_predict):
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.31,
                "confidence_band": "medium",
                "expected_performance_drop_window_laps": [8, 14],
                "reasons": ["Synthetic reason"],
            },
        }
        result = strategy_analyzer(2023, "Japanese Grand Prix", "R", "HAM", current_gap_seconds=1.0)

        self.assertFalse(result["fallback"])
        self.assertEqual(len(result["strategy"]["recommended_pit_window_laps"]), 2)
        self.assertIn(result["strategy"]["undercut_risk"], {"low", "medium", "high"})
        self.assertGreater(len(result["strategy"]["assumptions"]), 0)

    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_strategy_analyzer_fallback(self, mock_predict):
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "fallback": True,
            "fallback_reason": "No laps found",
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.0,
                "confidence_band": "low",
                "expected_performance_drop_window_laps": [0, 0],
                "reasons": ["No features"],
            },
        }
        result = strategy_analyzer(2023, "Japanese Grand Prix", "R", "HAM", current_gap_seconds=2.0)

        self.assertTrue(result["fallback"])
        self.assertEqual(result["strategy"]["undercut_risk"], "unknown")

    @patch("tools.strategy_helper.get_current_gap_to_ahead")
    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_strategy_analyzer_uses_live_gap_from_fastf1(self, mock_predict, mock_gap):
        # Slice 1A of #168: when caller doesn't pass current_gap_seconds we
        # call FastF1 once for the live number. Verify it flows into the
        # undercut classifier and surfaces in the response payload.
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2024,
            "event": "Bahrain Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.31,
                "confidence_band": "medium",
                "expected_performance_drop_window_laps": [8, 14],
                "reasons": [],
            },
        }
        mock_gap.return_value = {
            "gap_seconds": 1.4,
            "driver_ahead": "VER",
            "lap_number": 25,
            "fallback": False,
            "fallback_reason": None,
        }

        result = strategy_analyzer(2024, "Bahrain Grand Prix", "R", "HAM")

        mock_gap.assert_called_once_with(2024, "Bahrain Grand Prix", "R", "HAM")
        strategy = result["strategy"]
        self.assertEqual(strategy["gap_source"], "fastf1")
        self.assertEqual(strategy["competitor_ahead"], "VER")
        self.assertEqual(strategy["gap_sampled_at_lap"], 25)
        self.assertEqual(strategy["current_gap_seconds"], 1.4)
        # Gap 1.4s + degradation 0.31 → high undercut.
        self.assertEqual(strategy["undercut_risk"], "high")
        self.assertIn("VER", strategy["assumptions"][0])

    @patch("tools.strategy_helper.get_current_gap_to_ahead")
    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_strategy_analyzer_falls_back_to_default_gap(self, mock_predict, mock_gap):
        # When FastF1 is offline we keep the legacy 1.2s assumption so the
        # undercut/overcut bands still make a call, just with low confidence.
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2024,
            "event": "Bahrain Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.20,
                "confidence_band": "medium",
                "expected_performance_drop_window_laps": [8, 14],
                "reasons": [],
            },
        }
        mock_gap.return_value = {
            "gap_seconds": None,
            "driver_ahead": None,
            "lap_number": None,
            "fallback": True,
            "fallback_reason": "FastF1 cache miss",
        }

        result = strategy_analyzer(2024, "Bahrain Grand Prix", "R", "HAM")

        strategy = result["strategy"]
        self.assertEqual(strategy["gap_source"], "fallback")
        self.assertIsNone(strategy["competitor_ahead"])
        self.assertEqual(strategy["current_gap_seconds"], 1.2)

    @patch("tools.strategy_helper.get_current_gap_to_ahead")
    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_strategy_analyzer_explicit_gap_skips_fastf1(self, mock_predict, mock_gap):
        # Tests + what-if scenarios pass an explicit gap. We must not
        # call FastF1 in that case — it would burn a session.load() per
        # parametrised test run.
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2024,
            "event": "Bahrain Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.20,
                "confidence_band": "medium",
                "expected_performance_drop_window_laps": [8, 14],
                "reasons": [],
            },
        }

        result = strategy_analyzer(
            2024, "Bahrain Grand Prix", "R", "HAM", current_gap_seconds=3.0
        )

        mock_gap.assert_not_called()
        self.assertEqual(result["strategy"]["gap_source"], "explicit")
        self.assertEqual(result["strategy"]["current_gap_seconds"], 3.0)
        self.assertEqual(result["strategy"]["undercut_risk"], "low")

    @patch("tools.strategy_helper.get_gap_to_competitor")
    @patch("tools.strategy_helper.get_current_gap_to_ahead")
    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_strategy_analyzer_uses_target_competitor(self, mock_predict, mock_ahead, mock_competitor):
        # Slice 1B of #168: when target_driver is set we should call the
        # competitor-specific helper and ignore the "ahead" lookup.
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2024,
            "event": "Bahrain Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.30,
                "confidence_band": "medium",
                "expected_performance_drop_window_laps": [8, 14],
                "reasons": [],
            },
        }
        mock_competitor.return_value = {
            "gap_seconds": 1.4,
            "competitor_position_relative": "ahead",
            "lap_number": 25,
            "fallback": False,
            "fallback_reason": None,
        }

        result = strategy_analyzer(
            2024, "Bahrain Grand Prix", "R", "HAM", target_driver="ver"
        )

        mock_competitor.assert_called_once_with(
            2024, "Bahrain Grand Prix", "R", "HAM", "ver"
        )
        mock_ahead.assert_not_called()
        strategy = result["strategy"]
        self.assertEqual(strategy["gap_source"], "fastf1")
        self.assertEqual(strategy["competitor_ahead"], "VER")
        self.assertEqual(strategy["competitor_position_relative"], "ahead")
        self.assertEqual(strategy["current_gap_seconds"], 1.4)
        self.assertEqual(strategy["undercut_risk"], "high")

    @patch("tools.strategy_helper.get_gap_to_competitor")
    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_target_competitor_fallback_drops_competitor_label(self, mock_predict, mock_competitor):
        # When FastF1 falls back the gap value is synthetic — we must NOT
        # attribute the 1.2s to a named driver, because the assumption
        # string would then read "Current gap to VER: 1.2s" which is a
        # lie. Reverts to the generic "rival considered" wording.
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2024,
            "event": "Bahrain Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.20,
                "confidence_band": "medium",
                "expected_performance_drop_window_laps": [8, 14],
                "reasons": [],
            },
        }
        mock_competitor.return_value = {
            "gap_seconds": None,
            "competitor_position_relative": None,
            "lap_number": None,
            "fallback": True,
            "fallback_reason": "FastF1 down",
        }

        result = strategy_analyzer(
            2024, "Bahrain Grand Prix", "R", "HAM", target_driver="VER"
        )

        strategy = result["strategy"]
        self.assertEqual(strategy["gap_source"], "fallback")
        self.assertIsNone(strategy["competitor_ahead"])
        self.assertEqual(strategy["current_gap_seconds"], 1.2)
        # Assumption must not name the picked driver alongside a synthetic gap.
        self.assertNotIn("VER", strategy["assumptions"][0])


    @patch("tools.strategy_helper.get_gap_to_competitor")
    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_strategy_analyzer_surfaces_pit_loss_and_undercut_estimate(
        self, mock_predict, mock_competitor
    ):
        # Slice 1C of #168: pit_loss_seconds + undercut_break_even_laps
        # are wired onto the strategy payload when chasing a competitor.
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2024,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.30,
                "confidence_band": "medium",
                "expected_performance_drop_window_laps": [8, 14],
                "reasons": [],
            },
        }
        mock_competitor.return_value = {
            "gap_seconds": 1.4,
            "competitor_position_relative": "ahead",
            "lap_number": 25,
            "fallback": False,
            "fallback_reason": None,
        }

        result = strategy_analyzer(
            2024, "Japanese Grand Prix", "R", "HAM", target_driver="VER"
        )

        strategy = result["strategy"]
        # Japan = 22s pit loss; advantage ~0.8s/lap → 2-lap break-even.
        self.assertEqual(strategy["pit_loss_seconds"], 22.0)
        self.assertEqual(strategy["undercut_break_even_laps"], 2)

    @patch("tools.strategy_helper.get_gap_to_competitor")
    @patch("tools.strategy_helper.predict_tyre_wear")
    def test_undercut_estimate_hidden_when_competitor_is_behind(
        self, mock_predict, mock_competitor
    ):
        # If the rival is BEHIND, undercut math doesn't apply — the panel
        # should still show pit_loss_seconds (it's a track property) but
        # leave undercut_break_even_laps unset so the UI hides the line.
        mock_predict.return_value = {
            "driver": "HAM",
            "year": 2024,
            "event": "Bahrain Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.20,
                "confidence_band": "medium",
                "expected_performance_drop_window_laps": [8, 14],
                "reasons": [],
            },
        }
        mock_competitor.return_value = {
            "gap_seconds": 2.0,
            "competitor_position_relative": "behind",
            "lap_number": 25,
            "fallback": False,
            "fallback_reason": None,
        }

        result = strategy_analyzer(
            2024, "Bahrain Grand Prix", "R", "HAM", target_driver="NOR"
        )

        strategy = result["strategy"]
        self.assertEqual(strategy["pit_loss_seconds"], 22.0)
        self.assertIsNone(strategy["undercut_break_even_laps"])


if __name__ == "__main__":
    unittest.main()
