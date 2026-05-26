"""Tests for the cross-year lap-delta helper (#229)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from tools.lap_delta_cross_year import compute_cross_year_lap_delta


def _fake_car_telemetry(distance_end: float = 5000.0, samples: int = 200, speedup: float = 1.0):
    """Mirror tests.test_lap_delta._fake_car_telemetry shape."""
    distance = np.linspace(0.0, distance_end, samples)
    session_time = pd.to_timedelta(distance / 50.0 / speedup, unit="s")
    return pd.DataFrame({"Distance": distance, "SessionTime": session_time})


def _fake_lap_with_telemetry(
    *, lap_number: int = 5, lap_time_seconds: float | None = 90.0, telemetry=None
):
    lap = MagicMock()
    lap.empty = False
    lap.__getitem__.side_effect = lambda key: {
        "LapNumber": lap_number,
        "LapTime": pd.Timedelta(seconds=lap_time_seconds) if lap_time_seconds is not None else None,
    }[key]
    lap.get_car_data.return_value.add_distance.return_value = telemetry
    return lap


def _fake_session_with_lap(driver_lap_map: dict[str, MagicMock | None]):
    """Build a MagicMock session whose pick_drivers returns appropriate laps."""

    def pick_drivers(driver_code):
        lap = driver_lap_map.get(driver_code)
        laps_mock = MagicMock()
        if lap is None:
            laps_mock.empty = True
        else:
            laps_mock.empty = False
            laps_mock.pick_fastest.return_value = lap
        return laps_mock

    session = MagicMock()
    session.laps.pick_drivers.side_effect = pick_drivers
    return session


class ComputeCrossYearLapDeltaTests(unittest.TestCase):
    def test_same_year_returns_fallback(self):
        result = compute_cross_year_lap_delta(
            event="Silverstone", session_type="R", driver="HAM", year_a=2024, year_b=2024,
        )
        self.assertTrue(result["fallback"])
        self.assertIn("same", result["fallback_reason"].lower())

    @patch("tools.lap_delta_cross_year.fastf1.get_session")
    def test_first_session_load_failure_returns_fallback(self, mock_get_session):
        mock_get_session.side_effect = RuntimeError("network oops")
        result = compute_cross_year_lap_delta(
            event="Silverstone", session_type="R", driver="HAM", year_a=2023, year_b=2024,
        )
        self.assertTrue(result["fallback"])
        self.assertIn("2023", result["fallback_reason"])
        self.assertIn("network oops", result["fallback_reason"])

    @patch("tools.lap_delta_cross_year.fastf1.get_session")
    def test_second_session_load_failure_returns_fallback(self, mock_get_session):
        first_session = _fake_session_with_lap({
            "HAM": _fake_lap_with_telemetry(telemetry=_fake_car_telemetry())
        })

        def side_effect(year, *_args, **_kwargs):
            if year == 2023:
                return first_session
            raise RuntimeError("boom in 2024")

        mock_get_session.side_effect = side_effect

        result = compute_cross_year_lap_delta(
            event="Silverstone", session_type="R", driver="HAM", year_a=2023, year_b=2024,
        )
        self.assertTrue(result["fallback"])
        self.assertIn("2024", result["fallback_reason"])

    @patch("tools.lap_delta_cross_year.fastf1.get_session")
    def test_missing_telemetry_for_year_a_returns_fallback(self, mock_get_session):
        session_a = _fake_session_with_lap({"HAM": None})  # rookie / DNQ
        session_b = _fake_session_with_lap({
            "HAM": _fake_lap_with_telemetry(telemetry=_fake_car_telemetry())
        })

        def side_effect(year, *_a, **_kw):
            return session_a if year == 2023 else session_b

        mock_get_session.side_effect = side_effect

        result = compute_cross_year_lap_delta(
            event="Silverstone", session_type="R", driver="HAM", year_a=2023, year_b=2024,
        )
        self.assertTrue(result["fallback"])
        self.assertIn("2023", result["fallback_reason"])
        self.assertIn("HAM", result["fallback_reason"])

    @patch("tools.lap_delta_cross_year.fastf1.get_session")
    def test_returns_delta_arrays_with_expected_sign(self, mock_get_session):
        # year_a baseline, year_b 0.5% slower → year_b should accumulate
        # positive Δ along the lap, ending around +0.5s.
        tel_a = _fake_car_telemetry(speedup=1.0)
        tel_b = _fake_car_telemetry(speedup=0.995)

        session_a = _fake_session_with_lap({
            "HAM": _fake_lap_with_telemetry(lap_number=12, lap_time_seconds=90.0, telemetry=tel_a),
        })
        session_b = _fake_session_with_lap({
            "HAM": _fake_lap_with_telemetry(lap_number=18, lap_time_seconds=90.5, telemetry=tel_b),
        })

        def side_effect(year, *_a, **_kw):
            return session_a if year == 2023 else session_b

        mock_get_session.side_effect = side_effect

        result = compute_cross_year_lap_delta(
            event="Silverstone", session_type="R", driver="HAM", year_a=2023, year_b=2024,
        )

        self.assertFalse(result["fallback"])
        self.assertEqual(result["driver"], "HAM")
        self.assertEqual(result["year_a"], 2023)
        self.assertEqual(result["year_b"], 2024)
        self.assertEqual(result["lap_a"], 12)
        self.assertEqual(result["lap_b"], 18)
        self.assertAlmostEqual(result["lap_time_a_seconds"], 90.0, places=2)
        self.assertAlmostEqual(result["lap_time_b_seconds"], 90.5, places=2)
        self.assertEqual(len(result["distance_m"]), 250)
        self.assertEqual(len(result["delta_seconds"]), 250)
        self.assertAlmostEqual(result["delta_seconds"][0], 0.0, places=2)
        self.assertGreater(result["delta_seconds"][-1], 0.3)
        self.assertLess(result["delta_seconds"][-1], 0.7)


if __name__ == "__main__":
    unittest.main()
