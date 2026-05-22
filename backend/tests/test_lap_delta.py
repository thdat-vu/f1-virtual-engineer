"""Tests for the per-distance lap-delta helper (#184)."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd

from tools.lap_delta import compute_lap_delta


def _fake_car_telemetry(distance_end: float = 5000.0, samples: int = 200, speedup: float = 1.0):
    """Build a DataFrame mimicking ``Lap.get_car_data().add_distance()``.

    ``speedup`` lets a test simulate a faster lap by compressing time —
    same distance covered in less time.
    """
    distance = np.linspace(0.0, distance_end, samples)
    # Roughly 100s lap → 50 m/s mean ⇒ session_time = distance / 50 / speedup.
    session_time = pd.to_timedelta(distance / 50.0 / speedup, unit="s")
    return pd.DataFrame({"Distance": distance, "SessionTime": session_time})


class ComputeLapDeltaTests(unittest.TestCase):
    def test_same_driver_returns_fallback(self):
        result = compute_lap_delta(
            2024, "Bahrain Grand Prix", "R", "VER", "VER"
        )
        self.assertTrue(result["fallback"])
        self.assertIn("same", result["fallback_reason"].lower())

    @patch("tools.lap_delta.fastf1.get_session")
    def test_session_load_failure_returns_fallback(self, mock_get_session):
        # FastF1 raises a long tree of exceptions; we coerce all to the
        # fail-closed envelope so the API never 5xxs.
        mock_get_session.side_effect = RuntimeError("network oops")
        result = compute_lap_delta(
            2024, "Bahrain Grand Prix", "R", "VER", "HAM"
        )
        self.assertTrue(result["fallback"])
        self.assertIn("network oops", result["fallback_reason"])

    @patch("tools.lap_delta.fastf1.get_session")
    def test_missing_telemetry_for_one_driver_returns_fallback(self, mock_get_session):
        session = MagicMock()
        ref_lap = MagicMock()
        ref_lap.empty = False
        ref_lap.__getitem__.return_value = 5
        ref_lap.get_car_data.return_value.add_distance.return_value = _fake_car_telemetry()

        # Compare driver: pick_drivers returns empty (driver retired).
        ref_laps = MagicMock()
        ref_laps.empty = False
        ref_laps.pick_fastest.return_value = ref_lap
        cmp_laps = MagicMock()
        cmp_laps.empty = True

        def pick_drivers(d):
            return ref_laps if d == "VER" else cmp_laps

        session.laps.pick_drivers.side_effect = pick_drivers
        mock_get_session.return_value = session

        result = compute_lap_delta(
            2024, "Bahrain Grand Prix", "R", "VER", "HAM"
        )
        self.assertTrue(result["fallback"])
        self.assertIn("HAM", result["fallback_reason"])

    @patch("tools.lap_delta.fastf1.get_session")
    def test_returns_delta_arrays_with_expected_sign(self, mock_get_session):
        # Reference driver runs the lap in ~100s; compare runs the same
        # lap 0.5s slower (speedup < 1). Δ should be uniformly positive
        # and end at ~+0.5s, give or take rounding.
        ref_tel = _fake_car_telemetry(speedup=1.0)
        cmp_tel = _fake_car_telemetry(speedup=0.995)  # ~0.5% slower

        ref_lap = MagicMock()
        ref_lap.empty = False
        ref_lap.__getitem__.return_value = 5  # LapNumber
        ref_lap.get_car_data.return_value.add_distance.return_value = ref_tel
        cmp_lap = MagicMock()
        cmp_lap.empty = False
        cmp_lap.__getitem__.return_value = 5
        cmp_lap.get_car_data.return_value.add_distance.return_value = cmp_tel

        ref_laps = MagicMock(); ref_laps.empty = False; ref_laps.pick_fastest.return_value = ref_lap
        cmp_laps = MagicMock(); cmp_laps.empty = False; cmp_laps.pick_fastest.return_value = cmp_lap

        def pick_drivers(d):
            return ref_laps if d == "VER" else cmp_laps

        session = MagicMock()
        session.laps.pick_drivers.side_effect = pick_drivers
        mock_get_session.return_value = session

        result = compute_lap_delta(
            2024, "Bahrain Grand Prix", "R", "VER", "HAM"
        )

        self.assertFalse(result["fallback"])
        self.assertEqual(result["reference_driver"], "VER")
        self.assertEqual(result["compare_driver"], "HAM")
        self.assertEqual(len(result["distance_m"]), 250)
        self.assertEqual(len(result["delta_seconds"]), 250)
        # Ends at zero by construction (laps start at zero); compare
        # should be increasingly behind, so the final delta is positive
        # and larger than the start.
        self.assertAlmostEqual(result["delta_seconds"][0], 0.0, places=2)
        self.assertGreater(result["delta_seconds"][-1], 0.3)
        self.assertLess(result["delta_seconds"][-1], 0.7)


if __name__ == "__main__":
    unittest.main()
