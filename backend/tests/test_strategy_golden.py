"""
pytest entry for the strategy golden eval.

Two layers:
- `test_compare_*` exercises the comparison logic with hand-built actual/expected pairs (fast, no FastF1).
- `test_strategy_golden_runs_clean` runs the full golden set against the live strategy_analyzer using cached FastF1 data (slower, requires backend/data cache).

The full-run test will skip if the cache is unavailable so contributors can run unit tests offline without the cache.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from eval.run_strategy_eval import (
    GOLDEN_PATH,
    PIT_WINDOW_TOLERANCE_LAPS,
    DEGRADATION_TOLERANCE_SECONDS,
    _compare,
    run_eval,
)


SAMPLE_CASE = {
    "id": "fixture",
    "year": 2023,
    "event": "Japanese Grand Prix",
    "session_type": "R",
    "driver": "VER",
    "expected": {
        "fallback": False,
        "pit_window": [12, 18],
        "undercut_risk": "medium",
        "overcut_risk": "low",
        "confidence_band": "high",
        "degradation_rate_seconds_per_lap": 0.0,
    },
}


def _actual(pit_window=(12, 18), undercut="medium", overcut="low", confidence="high", degradation=0.0, fallback=False):
    return {
        "driver": "VER",
        "fallback": fallback,
        "fallback_reason": None,
        "strategy": {
            "recommended_pit_window_laps": list(pit_window),
            "undercut_risk": undercut,
            "overcut_risk": overcut,
            "confidence_band": confidence,
        },
        "tyre_prediction": {"degradation_rate_seconds_per_lap": degradation},
    }


class CompareTests(unittest.TestCase):
    def test_match_passes(self):
        result = _compare(SAMPLE_CASE, _actual())
        self.assertTrue(result.passed, result.failures)

    def test_pit_window_within_tolerance_passes(self):
        result = _compare(SAMPLE_CASE, _actual(pit_window=(12 + PIT_WINDOW_TOLERANCE_LAPS, 18 - PIT_WINDOW_TOLERANCE_LAPS)))
        self.assertTrue(result.passed, result.failures)

    def test_pit_window_outside_tolerance_fails(self):
        result = _compare(SAMPLE_CASE, _actual(pit_window=(12 + PIT_WINDOW_TOLERANCE_LAPS + 1, 18)))
        self.assertFalse(result.passed)
        self.assertTrue(any("pit_window start" in f for f in result.failures))

    def test_undercut_risk_mismatch_fails(self):
        result = _compare(SAMPLE_CASE, _actual(undercut="high"))
        self.assertFalse(result.passed)
        self.assertTrue(any("undercut_risk" in f for f in result.failures))

    def test_confidence_band_mismatch_fails(self):
        result = _compare(SAMPLE_CASE, _actual(confidence="low"))
        self.assertFalse(result.passed)
        self.assertTrue(any("confidence_band" in f for f in result.failures))

    def test_degradation_within_tolerance_passes(self):
        result = _compare(SAMPLE_CASE, _actual(degradation=DEGRADATION_TOLERANCE_SECONDS))
        self.assertTrue(result.passed, result.failures)

    def test_degradation_outside_tolerance_fails(self):
        result = _compare(SAMPLE_CASE, _actual(degradation=DEGRADATION_TOLERANCE_SECONDS + 0.01))
        self.assertFalse(result.passed)
        self.assertTrue(any("degradation_rate_seconds_per_lap" in f for f in result.failures))

    def test_fallback_mismatch_fails(self):
        result = _compare(SAMPLE_CASE, _actual(fallback=True))
        self.assertFalse(result.passed)
        self.assertTrue(any("fallback" in f for f in result.failures))


class GoldenSetTests(unittest.TestCase):
    def test_golden_file_is_well_formed(self):
        with GOLDEN_PATH.open() as f:
            cases = [json.loads(line) for line in f if line.strip()]
        self.assertGreaterEqual(len(cases), 5, "golden set must have at least 5 cases")
        ids = [c["id"] for c in cases]
        self.assertEqual(len(ids), len(set(ids)), "case ids must be unique")
        for c in cases:
            self.assertIn("year", c)
            self.assertIn("event", c)
            self.assertIn("session_type", c)
            self.assertIn("driver", c)
            self.assertIn("expected", c)

    def test_strategy_golden_runs_clean(self):
        cache_dir = Path(__file__).resolve().parent.parent / "data"
        if not cache_dir.exists() or not any(cache_dir.iterdir()):
            self.skipTest("FastF1 cache not present; skipping full-run eval.")
        results, summary = run_eval()
        failed = [r for r in results if not r.passed]
        self.assertFalse(
            failed,
            "\n".join(["Strategy golden drift detected:"] + summary),
        )


if __name__ == "__main__":
    unittest.main()
