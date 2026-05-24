"""Strategy pit-accuracy eval (#208).

Measures whether `strategy_analyzer`'s recommended pit window brackets the
actual first-stop lap of a real historical race within ±N laps. Unlike the
golden eval (which pins regression drift against captured baselines), this
harness compares against ground truth derived from FastF1 lap data —
answering "is the heuristic right?" rather than "did the heuristic
change?".

Opt-in via `RUN_STRATEGY_PIT_EVAL=1` because the cache lives under
`backend/data/` (gitignored). CI does not set the flag, so the harness is
silent in CI and only runs locally when invoked deliberately:

    RUN_STRATEGY_PIT_EVAL=1 python3 -m pytest backend/tests/test_strategy_pit_eval.py -s

The `-s` flag matters — the summary line ("X/N within ±2 laps") goes to
stdout via `print`, which pytest captures unless `-s` is passed.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from evals.cases.strategy_pit_fixtures import FIXTURES

PIT_LAP_TOLERANCE = 2


def _first_pit_in_lap(lap_list: dict) -> int | None:
    """Return the lap number of the first lap flagged `is_pit_in`, or None.

    FastF1's `PitInTime` column marks the lap on which the driver entered
    the pits — that's the lap we want to bracket. The pit OUT lap (one
    later) is what shows up as a fresh stint, but the strategist's
    decision is "in lap N, box this lap".
    """
    laps = lap_list.get("laps") or []
    for lap in laps:
        if lap.get("is_pit_in"):
            return int(lap["lap_number"])
    return None


def _cache_present() -> bool:
    cache_dir = _BACKEND_DIR / "data"
    return cache_dir.exists() and any(cache_dir.iterdir())


class StrategyPitAccuracyTests(unittest.TestCase):
    def test_pit_window_brackets_actual_first_stop(self):
        if os.environ.get("RUN_STRATEGY_PIT_EVAL") != "1":
            self.skipTest(
                "Strategy pit-accuracy eval is opt-in. "
                "Set RUN_STRATEGY_PIT_EVAL=1 to run; FastF1 cache lives "
                "under backend/data/ and is gitignored."
            )
        if not _cache_present():
            self.skipTest("FastF1 cache not present; skipping pit-accuracy eval.")

        from tools.fastf1_helper import get_session_lap_list
        from tools.strategy_helper import strategy_analyzer

        results: list[tuple[str, bool, str]] = []
        for fixture in FIXTURES:
            fixture_id = fixture["id"]
            lap_list = get_session_lap_list(
                year=fixture["year"],
                event=fixture["event"],
                session_type=fixture["session_type"],
                driver=fixture["driver"],
            )
            if lap_list.get("fallback"):
                results.append(
                    (fixture_id, False, f"lap data unavailable: {lap_list.get('fallback_reason')}")
                )
                continue

            actual_pit_lap = _first_pit_in_lap(lap_list)
            if actual_pit_lap is None:
                results.append((fixture_id, False, "no pit-in lap found in race data"))
                continue

            strategy = strategy_analyzer(
                year=fixture["year"],
                event=fixture["event"],
                session_type=fixture["session_type"],
                driver=fixture["driver"],
            )
            if strategy.get("fallback"):
                results.append(
                    (fixture_id, False, f"strategy fallback: {strategy.get('fallback_reason')}")
                )
                continue

            window = strategy.get("strategy", {}).get("recommended_pit_window_laps") or []
            if len(window) != 2:
                results.append((fixture_id, False, f"malformed pit window: {window!r}"))
                continue

            start, end = int(window[0]), int(window[1])
            covered = (start - PIT_LAP_TOLERANCE) <= actual_pit_lap <= (end + PIT_LAP_TOLERANCE)
            detail = f"recommended {start}-{end}, actual {actual_pit_lap}"
            results.append((fixture_id, covered, detail))

        passed = sum(1 for _, ok, _ in results if ok)
        total = len(results)
        pct = (100 * passed / total) if total else 0.0

        print(
            f"\nStrategy pit accuracy: {passed}/{total} scenarios within "
            f"±{PIT_LAP_TOLERANCE} laps tolerance ({pct:.0f}%)"
        )
        for fixture_id, ok, detail in results:
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {fixture_id}: {detail}")

        # Surface the number, don't gate the build on a coverage threshold
        # yet — the tolerance band may need calibration after the first
        # full run. Once we see a stable distribution we can flip this to
        # `assertGreaterEqual(passed, ceil(0.6 * total))` or similar.
        self.assertGreater(total, 0, "no fixtures evaluated")


if __name__ == "__main__":
    unittest.main()
