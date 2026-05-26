"""Tests for the weather helper (#235)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from tools.weather_helper import get_weather_summary


def _fake_weather_df(*, rainfall_pattern, air_temp=20.0, track_temp=30.0, humidity=60.0, wind=5.0):
    n = len(rainfall_pattern)
    return pd.DataFrame({
        "Time": pd.to_timedelta([i * 60 for i in range(n)], unit="s"),
        "AirTemp": [air_temp] * n,
        "Humidity": [humidity] * n,
        "Pressure": [1010.0] * n,
        "Rainfall": rainfall_pattern,
        "TrackTemp": [track_temp] * n,
        "WindDirection": [180] * n,
        "WindSpeed": [wind] * n,
    })


class GetWeatherSummaryTests(unittest.TestCase):
    @patch("tools.weather_helper.fastf1.get_session")
    def test_dry_session(self, mock_get_session):
        session = MagicMock()
        session.weather_data = _fake_weather_df(rainfall_pattern=[False] * 10, track_temp=42.0)
        mock_get_session.return_value = session

        result = get_weather_summary(2024, "Bahrain", "R")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["condition"], "DRY")
        self.assertEqual(result["rainfall_fraction"], 0.0)
        self.assertEqual(result["track_temp_c"], 42.0)

    @patch("tools.weather_helper.fastf1.get_session")
    def test_wet_session(self, mock_get_session):
        # 80% of samples have rain → WET
        session = MagicMock()
        session.weather_data = _fake_weather_df(
            rainfall_pattern=[True] * 8 + [False] * 2, track_temp=18.0,
        )
        mock_get_session.return_value = session

        result = get_weather_summary(2023, "Belgium", "R")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["condition"], "WET")
        self.assertEqual(result["rainfall_fraction"], 0.8)

    @patch("tools.weather_helper.fastf1.get_session")
    def test_mixed_session(self, mock_get_session):
        # 20% of samples have rain → MIXED (above 0%, below 30% threshold)
        session = MagicMock()
        session.weather_data = _fake_weather_df(
            rainfall_pattern=[True] * 2 + [False] * 8, track_temp=24.0,
        )
        mock_get_session.return_value = session

        result = get_weather_summary(2024, "Brazil", "R")

        self.assertFalse(result["fallback"])
        self.assertEqual(result["condition"], "MIXED")
        self.assertAlmostEqual(result["rainfall_fraction"], 0.2)

    @patch("tools.weather_helper.fastf1.get_session")
    def test_session_load_failure_returns_fallback(self, mock_get_session):
        mock_get_session.side_effect = RuntimeError("network down")

        result = get_weather_summary(2024, "Monza", "R")

        self.assertTrue(result["fallback"])
        self.assertIn("network down", result["fallback_reason"])
        self.assertIsNone(result["condition"])

    @patch("tools.weather_helper.fastf1.get_session")
    def test_empty_weather_data_returns_fallback(self, mock_get_session):
        session = MagicMock()
        session.weather_data = pd.DataFrame()
        mock_get_session.return_value = session

        result = get_weather_summary(2018, "Hockenheim", "FP1")

        self.assertTrue(result["fallback"])
        self.assertIn("weather samples", result["fallback_reason"].lower())

    @patch("tools.weather_helper.fastf1.get_session")
    def test_missing_weather_attr_returns_fallback(self, mock_get_session):
        session = MagicMock()
        session.weather_data = None
        mock_get_session.return_value = session

        result = get_weather_summary(2020, "Imola", "Q")

        self.assertTrue(result["fallback"])


if __name__ == "__main__":
    unittest.main()
