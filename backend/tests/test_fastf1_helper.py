import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from tools.fastf1_helper import (
    SERIES_POINTS,
    _downsample,
    _reset_caches_for_tests,
    extract_tyre_wear_features,
    get_current_gap_to_ahead,
    get_gap_to_competitor,
    get_session_lap_list,
    get_session_telemetry_summary,
)


class _FakeLaps(pd.DataFrame):
    """Minimal stand-in for fastf1.core.Laps.

    Adds the one method ``get_current_gap_to_ahead`` actually calls
    (`pick_driver`) so we can hand a real pandas DataFrame to the helper
    without dragging fastf1's full Laps subclass into the test fixture.
    The ``_constructor`` property keeps slices and ``.dropna()`` results
    inside the same subclass.
    """

    @property
    def _constructor(self):  # type: ignore[override]
        return _FakeLaps

    def pick_driver(self, driver: str) -> "_FakeLaps":
        return _FakeLaps(self[self["Driver"] == driver.upper()].copy())


class FastF1HelperTests(unittest.TestCase):
    def setUp(self) -> None:
        # The helpers now cache successful results (#100 slice B).
        # Wipe between tests so each one sees its own patched fixture.
        _reset_caches_for_tests()

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_get_session_telemetry_summary_success(self, mock_get_session):
        telemetry_df = pd.DataFrame(
            {
                "Speed": [250.0, 260.0, 255.0],
                "nGear": [7, 8, 7],
                "RPM": [12000, 12500, 12300],
            }
        )

        mock_lap = MagicMock()
        mock_lap.get_telemetry.return_value = telemetry_df

        mock_laps = MagicMock()
        mock_laps.empty = False
        mock_laps.pick_fastest.return_value = mock_lap

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = mock_laps
        mock_get_session.return_value = mock_session

        result = get_session_telemetry_summary(2023, "Japanese Grand Prix", "R", "ham")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["driver"], "HAM")
        self.assertEqual(result["sample_points"], 3)
        self.assertEqual(result["speed"]["unit"], "km/h")
        self.assertEqual(result["gear"]["unit"], "gear")
        self.assertEqual(result["rpm"]["unit"], "rpm")
        # Below SERIES_POINTS threshold the series is the raw values verbatim.
        self.assertEqual(result["speed"]["series"], [250.0, 260.0, 255.0])
        self.assertEqual(result["gear"]["series"], [7.0, 8.0, 7.0])

    def test_downsample_caps_series_length(self):
        big = pd.Series(range(1000), dtype=float)
        out = _downsample(big)
        self.assertEqual(len(out), SERIES_POINTS)
        # Mean-bucket aggregation must preserve overall min/max bounds.
        self.assertGreaterEqual(min(out), float(big.min()))
        self.assertLessEqual(max(out), float(big.max()))

    def test_downsample_passthrough_short_series(self):
        small = pd.Series([1.0, 2.0, 3.0])
        self.assertEqual(_downsample(small), [1.0, 2.0, 3.0])

    def test_downsample_empty_series(self):
        self.assertEqual(_downsample(pd.Series([], dtype=float)), [])

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_get_session_telemetry_summary_fallback_when_no_laps(self, mock_get_session):
        mock_laps = MagicMock()
        mock_laps.empty = True

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = mock_laps
        mock_get_session.return_value = mock_session

        result = get_session_telemetry_summary(2023, "Japanese Grand Prix", "R", "HAM")

        self.assertTrue(result["fallback"])
        self.assertEqual(result["sample_points"], 0)
        self.assertEqual(result["speed"]["avg"], 0.0)

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_get_session_telemetry_summary_picks_lap_when_lap_number_given(self, mock_get_session):
        # Two laps for the driver; we request lap_number=2 and expect that lap's telemetry.
        laps_df = pd.DataFrame({"LapNumber": [1, 2]})

        lap_one = MagicMock()
        lap_one.get_telemetry.return_value = pd.DataFrame(
            {"Speed": [200.0], "nGear": [6], "RPM": [10000]}
        )
        lap_two = MagicMock()
        lap_two.get_telemetry.return_value = pd.DataFrame(
            {"Speed": [300.0], "nGear": [8], "RPM": [13000]}
        )

        # Filtering by `LapNumber == lap_number` returns a one-row frame; `iloc[0]`
        # then gives us the chosen lap. We patch the filter to return the right row.
        mock_laps = MagicMock()
        mock_laps.empty = False
        mock_laps.__getitem__.return_value = mock_laps  # laps[laps["LapNumber"] == n]
        filtered = MagicMock()
        filtered.empty = False
        filtered.iloc.__getitem__.return_value = lap_two
        # Configure the comparison: laps["LapNumber"] == 2 -> truthy mask, then
        # laps[mask] -> filtered. We sidestep the mask plumbing by stubbing the
        # `__getitem__` chain to short-circuit to `filtered`.
        mock_laps.__getitem__.side_effect = lambda key: (
            filtered if not isinstance(key, str) else laps_df[key]
        )

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = mock_laps
        mock_get_session.return_value = mock_session

        result = get_session_telemetry_summary(
            2023, "Japanese Grand Prix", "R", "HAM", lap_number=2,
        )

        self.assertFalse(result["fallback"])
        self.assertEqual(result["lap_number"], 2)
        self.assertEqual(result["speed"]["max"], 300.0)
        lap_two.get_telemetry.assert_called_once()
        lap_one.get_telemetry.assert_not_called()

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_get_session_telemetry_summary_emits_lap_duration_and_sectors(self, mock_get_session):
        # Lap row exposes LapTime + Sector1Time + Sector2Time as real timedeltas.
        # _normalize_telemetry should derive lap_duration_s and sector_boundaries_s.
        telemetry_df = pd.DataFrame(
            {"Speed": [250.0, 260.0], "nGear": [7, 8], "RPM": [12000, 12500]}
        )
        chosen_lap = pd.Series({
            "LapNumber": 5,
            "LapTime": pd.Timedelta(seconds=86.161),
            "Sector1Time": pd.Timedelta(seconds=24.5),
            "Sector2Time": pd.Timedelta(seconds=29.3),
        })
        mock_lap = MagicMock()
        mock_lap.get_telemetry.return_value = telemetry_df
        # The helper reads sector/lap-time via .get() and the lap number via __getitem__/__contains__.
        mock_lap.get.side_effect = chosen_lap.get
        mock_lap.__getitem__.side_effect = chosen_lap.__getitem__
        mock_lap.__contains__.side_effect = chosen_lap.__contains__

        mock_laps = MagicMock()
        mock_laps.empty = False
        mock_laps.pick_fastest.return_value = mock_lap

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = mock_laps
        mock_get_session.return_value = mock_session

        result = get_session_telemetry_summary(2024, "Italian Grand Prix", "R", "GAS")

        self.assertFalse(result["fallback"])
        self.assertAlmostEqual(result["lap_duration_s"], 86.161, places=3)
        self.assertEqual(len(result["sector_boundaries_s"]), 2)
        self.assertAlmostEqual(result["sector_boundaries_s"][0], 24.5, places=3)
        self.assertAlmostEqual(result["sector_boundaries_s"][1], 24.5 + 29.3, places=3)

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_get_session_telemetry_summary_drops_sectors_when_missing(self, mock_get_session):
        # When sector times are NaT, the helper must emit an empty list rather than
        # half-populated boundaries that would mislead the chart x-axis.
        telemetry_df = pd.DataFrame(
            {"Speed": [200.0], "nGear": [6], "RPM": [10000]}
        )
        chosen_lap = pd.Series({
            "LapNumber": 1,
            "LapTime": pd.Timedelta(seconds=90.0),
            "Sector1Time": pd.NaT,
            "Sector2Time": pd.Timedelta(seconds=29.3),
        })
        mock_lap = MagicMock()
        mock_lap.get_telemetry.return_value = telemetry_df
        mock_lap.get.side_effect = chosen_lap.get
        mock_lap.__getitem__.side_effect = chosen_lap.__getitem__
        mock_lap.__contains__.side_effect = chosen_lap.__contains__

        mock_laps = MagicMock()
        mock_laps.empty = False
        mock_laps.pick_fastest.return_value = mock_lap

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = mock_laps
        mock_get_session.return_value = mock_session

        result = get_session_telemetry_summary(2024, "Italian Grand Prix", "R", "GAS")

        self.assertEqual(result["sector_boundaries_s"], [])
        self.assertAlmostEqual(result["lap_duration_s"], 90.0, places=3)

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_get_session_lap_list_success(self, mock_get_session):
        laps_df = pd.DataFrame(
            {
                "LapNumber": [1, 2, 3],
                "LapTime": pd.to_timedelta([95.4, 92.1, 92.6], unit="s"),
                "Compound": ["MEDIUM", "MEDIUM", "MEDIUM"],
                "PitInTime": [pd.NaT, pd.NaT, pd.NaT],
                "PitOutTime": [pd.Timedelta(seconds=2), pd.NaT, pd.NaT],
            }
        )
        fastest_lap = laps_df.iloc[1]

        mock_laps = MagicMock()
        mock_laps.empty = False
        mock_laps.iterrows.return_value = list(laps_df.iterrows())
        mock_laps.pick_fastest.return_value = fastest_lap

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = mock_laps
        mock_get_session.return_value = mock_session

        result = get_session_lap_list(2023, "Japanese Grand Prix", "R", "ham")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["driver"], "HAM")
        self.assertEqual(len(result["laps"]), 3)
        self.assertEqual(result["fastest_lap_number"], 2)
        self.assertEqual(result["laps"][0]["lap_number"], 1)
        self.assertAlmostEqual(result["laps"][0]["lap_time_seconds"], 95.4)
        self.assertTrue(result["laps"][0]["is_pit_out"])
        self.assertFalse(result["laps"][1]["is_pit_out"])

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_get_session_lap_list_fallback_when_empty(self, mock_get_session):
        mock_laps = MagicMock()
        mock_laps.empty = True

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = mock_laps
        mock_get_session.return_value = mock_session

        result = get_session_lap_list(2099, "Imaginary Grand Prix", "R", "HAM")

        self.assertTrue(result["fallback"])
        self.assertEqual(result["laps"], [])
        self.assertIsNone(result["fastest_lap_number"])

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_extract_tyre_wear_features_success(self, mock_get_session):
        laps_df = pd.DataFrame(
            {
                "LapTime": pd.to_timedelta([90.0, 90.4, 90.9], unit="s"),
                "Stint": [1, 1, 2],
            }
        )
        weather_df = pd.DataFrame({"TrackTemp": [32.0, 33.0, 35.0]})

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = laps_df
        mock_session.weather_data = weather_df
        mock_get_session.return_value = mock_session

        result = extract_tyre_wear_features(2023, "Japanese Grand Prix", "R", "HAM")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["features"]["lap_count"], 3)
        self.assertEqual(result["features"]["stint_count"], 2)
        self.assertFalse(result["features"]["temperature_missing"])
        self.assertIsNotNone(result["features"]["avg_track_temp_c"])

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_extract_tyre_wear_features_marks_missing_temperature(self, mock_get_session):
        laps_df = pd.DataFrame(
            {
                "LapTime": pd.to_timedelta([90.0, 90.2], unit="s"),
                "Stint": [1, 1],
            }
        )
        weather_df = pd.DataFrame({"AirTemp": [24.0, 24.5]})

        mock_session = MagicMock()
        mock_session.laps.pick_driver.return_value = laps_df
        mock_session.weather_data = weather_df
        mock_get_session.return_value = mock_session

        result = extract_tyre_wear_features(2023, "Japanese Grand Prix", "R", "HAM")

        self.assertFalse(result["fallback"])
        self.assertTrue(result["features"]["temperature_missing"])
        self.assertIsNone(result["features"]["avg_track_temp_c"])


class GetCurrentGapToAheadTests(unittest.TestCase):
    """Slice 1A of #168: live gap to driver ahead from FastF1.

    Tests build a small ``Laps`` frame with two drivers on the same lap
    and assert the helper picks the correct row pair, diffs ``Time``,
    and surfaces the competitor code. Failure modes (no laps, leader,
    fastf1 raising) all need to resolve to a populated envelope so the
    strategy_analyzer can degrade rather than 5xx.
    """

    def setUp(self) -> None:
        _reset_caches_for_tests()

    def _make_session(self, laps_df: pd.DataFrame) -> MagicMock:
        session = MagicMock()
        session.load = MagicMock()
        session.laps = _FakeLaps(laps_df)
        return session

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_returns_gap_and_competitor_when_running_p2(self, mock_get_session):
        # Two laps logged: HAM behind VER on lap 25, ~1.4s gap.
        laps_df = pd.DataFrame(
            {
                "Driver":    ["VER", "HAM", "VER", "HAM"],
                "LapNumber": [24,    24,    25,    25],
                "Position":  [1.0,   2.0,   1.0,   2.0],
                "Time":      pd.to_timedelta([1500.0, 1501.5, 1590.0, 1591.4], unit="s"),
            }
        )
        mock_get_session.return_value = self._make_session(laps_df)

        result = get_current_gap_to_ahead(2024, "Bahrain Grand Prix", "R", "ham")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["driver_ahead"], "VER")
        self.assertEqual(result["lap_number"], 25)
        self.assertAlmostEqual(result["gap_seconds"], 1.4, places=2)

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_leader_returns_none_gap_no_fallback(self, mock_get_session):
        laps_df = pd.DataFrame(
            {
                "Driver":    ["HAM"],
                "LapNumber": [10],
                "Position":  [1.0],
                "Time":      pd.to_timedelta([900.0], unit="s"),
            }
        )
        mock_get_session.return_value = self._make_session(laps_df)

        result = get_current_gap_to_ahead(2024, "Bahrain Grand Prix", "R", "HAM")

        self.assertFalse(result["fallback"])
        self.assertIsNone(result["gap_seconds"])
        self.assertIsNone(result["driver_ahead"])
        self.assertEqual(result["lap_number"], 10)

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_fastf1_exception_is_fail_closed(self, mock_get_session):
        mock_get_session.side_effect = RuntimeError("FastF1 cache miss; offline")

        result = get_current_gap_to_ahead(2024, "Bahrain Grand Prix", "R", "HAM")

        self.assertTrue(result["fallback"])
        self.assertIn("FastF1", result["fallback_reason"])
        self.assertIsNone(result["gap_seconds"])

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_missing_position_column_falls_back(self, mock_get_session):
        laps_df = pd.DataFrame(
            {
                "Driver":    ["HAM"],
                "LapNumber": [10],
                "Time":      pd.to_timedelta([900.0], unit="s"),
            }
        )
        mock_get_session.return_value = self._make_session(laps_df)

        result = get_current_gap_to_ahead(2024, "Bahrain Grand Prix", "R", "HAM")

        self.assertTrue(result["fallback"])
        self.assertIsNone(result["gap_seconds"])


class GetGapToCompetitorTests(unittest.TestCase):
    """Slice 1B of #168: signed gap to a user-picked competitor."""

    def setUp(self) -> None:
        _reset_caches_for_tests()

    def _make_session(self, laps_df: pd.DataFrame) -> MagicMock:
        session = MagicMock()
        session.load = MagicMock()
        session.laps = _FakeLaps(laps_df)
        return session

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_returns_positive_gap_when_competitor_is_ahead(self, mock_get_session):
        # HAM crossed the line 1.4s after VER on lap 25 → competitor ahead.
        laps_df = pd.DataFrame(
            {
                "Driver":    ["VER", "HAM", "VER", "HAM"],
                "LapNumber": [24,    24,    25,    25],
                "Time":      pd.to_timedelta([1500.0, 1501.5, 1590.0, 1591.4], unit="s"),
            }
        )
        mock_get_session.return_value = self._make_session(laps_df)

        result = get_gap_to_competitor(2024, "Bahrain Grand Prix", "R", "ham", "ver")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["competitor_position_relative"], "ahead")
        self.assertAlmostEqual(result["gap_seconds"], 1.4, places=2)
        self.assertEqual(result["lap_number"], 25)

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_returns_behind_when_competitor_is_behind(self, mock_get_session):
        # NOR is 2.0s behind HAM on lap 25 → competitor behind.
        laps_df = pd.DataFrame(
            {
                "Driver":    ["HAM", "NOR"],
                "LapNumber": [25,    25],
                "Time":      pd.to_timedelta([1591.0, 1593.0], unit="s"),
            }
        )
        mock_get_session.return_value = self._make_session(laps_df)

        result = get_gap_to_competitor(2024, "Bahrain Grand Prix", "R", "HAM", "NOR")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["competitor_position_relative"], "behind")
        self.assertAlmostEqual(result["gap_seconds"], 2.0, places=2)

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_falls_back_when_no_shared_laps(self, mock_get_session):
        # HAM lap 25, NOR lap 24 → no shared lap (NOR retired before HAM's last).
        laps_df = pd.DataFrame(
            {
                "Driver":    ["HAM", "NOR"],
                "LapNumber": [25,    24],
                "Time":      pd.to_timedelta([1591.0, 1500.0], unit="s"),
            }
        )
        mock_get_session.return_value = self._make_session(laps_df)

        result = get_gap_to_competitor(2024, "Bahrain Grand Prix", "R", "HAM", "NOR")

        self.assertTrue(result["fallback"])
        self.assertIsNone(result["gap_seconds"])

    def test_same_driver_returns_self_compare_fallback(self):
        # No FastF1 call needed — guard short-circuits before session.load().
        result = get_gap_to_competitor(2024, "Bahrain Grand Prix", "R", "HAM", "HAM")
        self.assertTrue(result["fallback"])
        self.assertEqual(result["gap_seconds"], 0.0)

    @patch("tools.fastf1_helper.fastf1.get_session")
    def test_fastf1_exception_is_fail_closed(self, mock_get_session):
        mock_get_session.side_effect = RuntimeError("FastF1 cache miss")
        result = get_gap_to_competitor(2024, "Bahrain Grand Prix", "R", "HAM", "VER")
        self.assertTrue(result["fallback"])
        self.assertIsNone(result["gap_seconds"])


if __name__ == "__main__":
    unittest.main()
