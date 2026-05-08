"""
Strategy golden-set runner.

Loads cases from `strategy_golden.jsonl`, invokes `tools.strategy_helper.strategy_analyzer`
for each, and asserts the response matches the captured baseline within a tolerance band.

Designed to:
- run offline against the FastF1 cache committed under backend/data/,
- catch unintentional drift in tyre-wear / strategy heuristics,
- be invoked from CLI (exit 0/1) or pytest (raises AssertionError).

Tolerance:
- pit_window endpoints may differ by up to PIT_WINDOW_TOLERANCE_LAPS (default 2),
- degradation rate may differ by up to DEGRADATION_TOLERANCE_SECONDS (default 0.05),
- categorical fields (undercut_risk, overcut_risk, confidence_band, fallback) must match exactly.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running this file directly (`python3 backend/eval/run_strategy_eval.py`).
# When invoked via pytest from the backend dir the path is already on sys.path.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

GOLDEN_PATH = Path(__file__).parent / "strategy_golden.jsonl"
PIT_WINDOW_TOLERANCE_LAPS = 2
DEGRADATION_TOLERANCE_SECONDS = 0.05


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    failures: list[str] = field(default_factory=list)


def _load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            cases.append(json.loads(line))
    return cases


def _compare(case: dict[str, Any], actual: dict[str, Any]) -> CaseResult:
    case_id = case["id"]
    expected = case["expected"]
    failures: list[str] = []

    actual_fallback = bool(actual.get("fallback", False))
    if actual_fallback != expected["fallback"]:
        failures.append(f"fallback: expected {expected['fallback']}, got {actual_fallback} (reason: {actual.get('fallback_reason')!r})")

    strategy = actual.get("strategy") or {}
    actual_pw = strategy.get("recommended_pit_window_laps") or []
    expected_pw = expected["pit_window"]
    if len(actual_pw) != 2:
        failures.append(f"pit_window: expected 2-element list, got {actual_pw!r}")
    else:
        for i, label in enumerate(("start", "end")):
            if abs(actual_pw[i] - expected_pw[i]) > PIT_WINDOW_TOLERANCE_LAPS:
                failures.append(
                    f"pit_window {label}: expected {expected_pw[i]} +/- {PIT_WINDOW_TOLERANCE_LAPS}, got {actual_pw[i]}"
                )

    for cat in ("undercut_risk", "overcut_risk", "confidence_band"):
        if strategy.get(cat) != expected[cat]:
            failures.append(f"{cat}: expected {expected[cat]!r}, got {strategy.get(cat)!r}")

    actual_deg = float(actual.get("tyre_prediction", {}).get("degradation_rate_seconds_per_lap", 0.0))
    expected_deg = float(expected["degradation_rate_seconds_per_lap"])
    if abs(actual_deg - expected_deg) > DEGRADATION_TOLERANCE_SECONDS:
        failures.append(
            f"degradation_rate_seconds_per_lap: expected {expected_deg} +/- {DEGRADATION_TOLERANCE_SECONDS}, got {actual_deg}"
        )

    return CaseResult(case_id=case_id, passed=not failures, failures=failures)


def run_eval(cases_path: Path = GOLDEN_PATH) -> tuple[list[CaseResult], list[str]]:
    """Run the golden eval. Returns (per-case results, summary lines)."""
    from tools.strategy_helper import strategy_analyzer

    cases = _load_cases(cases_path)
    results: list[CaseResult] = []

    for case in cases:
        actual = strategy_analyzer(
            year=case["year"],
            event=case["event"],
            session_type=case["session_type"],
            driver=case["driver"],
        )
        results.append(_compare(case, actual))

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    summary = [
        f"strategy-golden: {passed}/{len(results)} passed, {failed} failed",
    ]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        summary.append(f"  [{status}] {r.case_id}")
        for f in r.failures:
            summary.append(f"      - {f}")

    return results, summary


def main() -> int:
    results, summary = run_eval()
    for line in summary:
        print(line)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
