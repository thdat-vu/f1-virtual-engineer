"""Strategy pit-accuracy eval (#208 / #220).

Two opt-in run modes:

  RUN_STRATEGY_PIT_EVAL=1
    Live mode. Derives ground truth from FastF1 lap data and runs
    `strategy_analyzer` against the live cache. Used locally to
    regenerate the snapshot when fixtures change. CI does not run
    this — the FastF1 cache lives under `backend/data/` and is
    gitignored.

  STRATEGY_PIT_EVAL_SNAPSHOT=1
    CI mode. Reads `evals/cases/strategy_pit_groundtruth.json` for
    both the actual pit lap AND the tyre-feature envelope, then
    feeds the envelope into `predict_tyre_wear` via a monkey-patch
    of `extract_tyre_wear_features`. No FastF1 dependency.

    A regression below the threshold fails the build. The
    threshold is currently the live baseline minus a small slack
    so an unrelated heuristic refactor doesn't false-trip CI on a
    single-fixture nudge.

The window calculation depends only on tyre features + lap_count,
so snapshot mode and live mode produce identical PASS/FAIL.
Gap-derived fields (undercut_risk, expected_gain) differ between
modes — they are not part of the pit-window assertion.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from evals.cases.strategy_pit_fixtures import FIXTURES

PIT_LAP_TOLERANCE = 2

# Threshold for snapshot-mode CI gate. The current live baseline is
# 17/20; the threshold is set to the same number so any drop trips CI.
# Bump manually when the heuristic genuinely improves AND the snapshot
# is regenerated — keep the numbers in lockstep.
SNAPSHOT_PASS_THRESHOLD = 17

GROUNDTRUTH_PATH = (
    _BACKEND_DIR / "evals" / "cases" / "strategy_pit_groundtruth.json"
)


def _first_pit_in_lap(lap_list: dict) -> int | None:
    laps = lap_list.get("laps") or []
    for lap in laps:
        if lap.get("is_pit_in"):
            return int(lap["lap_number"])
    return None


def _cache_present() -> bool:
    cache_dir = _BACKEND_DIR / "data"
    return cache_dir.exists() and any(cache_dir.iterdir())


def _evaluate(
    actual_pit_lap: int,
    window: list[int],
) -> tuple[bool, str]:
    if len(window) != 2:
        return False, f"malformed pit window: {window!r}"
    start, end = int(window[0]), int(window[1])
    covered = (start - PIT_LAP_TOLERANCE) <= actual_pit_lap <= (end + PIT_LAP_TOLERANCE)
    return covered, f"recommended {start}-{end}, actual {actual_pit_lap}"


def _print_summary(
    mode: str, results: list[tuple[str, bool, str]]
) -> tuple[int, int]:
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    pct = (100 * passed / total) if total else 0.0
    print(
        f"\nStrategy pit accuracy [{mode}]: {passed}/{total} scenarios within "
        f"±{PIT_LAP_TOLERANCE} laps tolerance ({pct:.0f}%)"
    )
    for fixture_id, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {fixture_id}: {detail}")
    return passed, total


class StrategyPitAccuracyTests(unittest.TestCase):
    def test_pit_window_brackets_actual_first_stop_live(self):
        if os.environ.get("RUN_STRATEGY_PIT_EVAL") != "1":
            self.skipTest(
                "Live pit-accuracy eval is opt-in. "
                "Set RUN_STRATEGY_PIT_EVAL=1 to run; FastF1 cache lives "
                "under backend/data/ and is gitignored."
            )
        if not _cache_present():
            self.skipTest("FastF1 cache not present; skipping live eval.")

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
            ok, detail = _evaluate(actual_pit_lap, window)
            results.append((fixture_id, ok, detail))

        _print_summary("live", results)
        self.assertGreater(len(results), 0, "no fixtures evaluated")

    def test_pit_window_brackets_actual_first_stop_snapshot(self):
        if os.environ.get("STRATEGY_PIT_EVAL_SNAPSHOT") != "1":
            self.skipTest(
                "Snapshot pit-accuracy eval is opt-in. "
                "Set STRATEGY_PIT_EVAL_SNAPSHOT=1 to run "
                "(used by CI; no FastF1 dependency)."
            )

        # Loaded inside the test so import-time errors point at this test
        # rather than collection. Same import path as live mode.
        from tools.strategy_helper import predict_tyre_wear, strategy_analyzer

        with GROUNDTRUTH_PATH.open() as f:
            snapshot: dict[str, dict[str, Any]] = json.load(f)

        results: list[tuple[str, bool, str]] = []
        for fixture in FIXTURES:
            fixture_id = fixture["id"]
            entry = snapshot.get(fixture_id)
            if entry is None:
                results.append((fixture_id, False, "missing from groundtruth snapshot"))
                continue

            actual_pit_lap = int(entry["actual_first_pit_lap"])
            features_envelope = entry["tyre_features_envelope"]

            # Drive the strategy through the cached features. Bypassing
            # FastF1 entirely keeps the test offline; the gap is forced
            # to the legacy fallback so the window calculation depends
            # only on the captured features.
            with patch(
                "tools.strategy_helper.extract_tyre_wear_features",
                return_value=features_envelope,
            ):
                strategy = strategy_analyzer(
                    year=fixture["year"],
                    event=fixture["event"],
                    session_type=fixture["session_type"],
                    driver=fixture["driver"],
                    current_gap_seconds=1.2,
                )

            if strategy.get("fallback"):
                results.append(
                    (fixture_id, False, f"strategy fallback: {strategy.get('fallback_reason')}")
                )
                continue

            window = strategy.get("strategy", {}).get("recommended_pit_window_laps") or []
            ok, detail = _evaluate(actual_pit_lap, window)
            results.append((fixture_id, ok, detail))

        passed, total = _print_summary("snapshot", results)
        self.assertGreaterEqual(
            passed,
            SNAPSHOT_PASS_THRESHOLD,
            f"Strategy pit-accuracy regressed: {passed}/{total} passed, "
            f"threshold is {SNAPSHOT_PASS_THRESHOLD}/{total}. "
            "Either fix the heuristic or — if the change is intentional and "
            "you've regenerated the snapshot — bump SNAPSHOT_PASS_THRESHOLD.",
        )


if __name__ == "__main__":
    unittest.main()
