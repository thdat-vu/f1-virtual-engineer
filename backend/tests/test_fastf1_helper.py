import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from tools.fastf1_helper import (
    SERIES_POINTS,
    _downsample,
    extract_tyre_wear_features,
    get_session_lap_list,
    get_session_telemetry_summary,
)


class FastF1HelperTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
