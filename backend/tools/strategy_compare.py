"""Scenario what-if orchestrator for /strategy/compare (#202).

Composes the existing ``strategy_analyzer`` (pit-window + undercut math)
and ``knowledge_retriever`` (BM25 RAG) helpers — one invocation per
scenario — and packages the per-scenario outcomes for side-by-side
rendering.

Fail-closed at the scenario boundary: if ``strategy_analyzer`` raises or
returns a fallback envelope for one slot, the other scenarios still run
and only that slot carries ``fallback=True`` with a populated reason.
The endpoint never 5xxs because of one bad scenario.
"""

from __future__ import annotations

import logging
from typing import Any

from tools.knowledge_retriever import lookup as knowledge_lookup
from tools.strategy_helper import strategy_analyzer

_logger = logging.getLogger(__name__)


def _scenario_query(label: str) -> str:
    """Compose the BM25 query for a scenario's citation lookup.

    Use the label verbatim. An earlier draft appended generic strategy tokens
    ("pit window strategy undercut overcut tyre") to the label to bias toward
    the strategy corpus, but every scenario got the same suffix, which diluted
    the per-label signal — "Undercut" and "Overcut" queries ended up sharing
    five of six tokens and BM25 picked whichever doc had richer term-freq
    matches across them, ignoring the actual scenario name. The corpus has
    enough strategy-tagged entries that the label alone is doing the work.
    """

    return label


def _empty_outcome(label: str, reason: str) -> dict[str, Any]:
    return {
        "label": label,
        "recommended_pit_window_laps": [],
        "confidence_band": "low",
        "undercut_risk": "unknown",
        "overcut_risk": "unknown",
        "expected_gain_seconds": None,
        "undercut_break_even_laps": None,
        "current_gap_seconds": None,
        "gap_source": None,
        "citations": [],
        "fallback": True,
        "fallback_reason": reason,
    }


def _run_scenario(
    *,
    label: str,
    year: int,
    event: str,
    session_type: str,
    driver: str,
    target_driver: str | None,
    gap_override_seconds: float | None,
) -> dict[str, Any]:
    try:
        helper_result = strategy_analyzer(
            year=year,
            event=event,
            session_type=session_type,
            driver=driver,
            current_gap_seconds=gap_override_seconds,
            target_driver=target_driver,
        )
    except Exception as exc:  # noqa: BLE001 — fail-closed at scenario boundary
        _logger.warning("strategy_analyzer raised for scenario %r", label, exc_info=True)
        return _empty_outcome(label, f"strategy_analyzer raised: {exc}")

    if helper_result.get("fallback"):
        return _empty_outcome(
            label,
            helper_result.get("fallback_reason") or "strategy_analyzer fell back",
        )

    strategy = helper_result.get("strategy") or {}

    # Citation lookup is best-effort — a retrieval miss is not a scenario
    # failure, it just means no precedent to cite for this option.
    try:
        citations = knowledge_lookup(_scenario_query(label), 2) or []
    except Exception:  # noqa: BLE001
        _logger.warning("knowledge_lookup raised for scenario %r", label, exc_info=True)
        citations = []

    return {
        "label": label,
        "recommended_pit_window_laps": list(strategy.get("recommended_pit_window_laps") or []),
        "confidence_band": strategy.get("confidence_band") or "low",
        "undercut_risk": strategy.get("undercut_risk") or "unknown",
        "overcut_risk": strategy.get("overcut_risk") or "unknown",
        "expected_gain_seconds": strategy.get("expected_gain_seconds"),
        "undercut_break_even_laps": strategy.get("undercut_break_even_laps"),
        "current_gap_seconds": strategy.get("current_gap_seconds"),
        "gap_source": strategy.get("gap_source"),
        "citations": citations,
        "fallback": False,
        "fallback_reason": None,
    }


def compare_scenarios(
    *,
    year: int,
    event: str,
    session_type: str,
    driver: str,
    target_driver: str | None,
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run ``strategy_analyzer`` once per scenario, attach citations, return outcomes.

    Each ``scenarios`` item is treated as ``ScenarioSpec`` (see
    ``app.schemas.strategy_compare``). A scenario's own ``target_driver``
    overrides the request-level default; ``gap_override_seconds`` is
    passed straight through to the helper as ``current_gap_seconds``.
    """

    outcomes: list[dict[str, Any]] = []
    for spec in scenarios:
        scenario_target = spec.get("target_driver") or target_driver
        outcomes.append(
            _run_scenario(
                label=str(spec["label"]),
                year=year,
                event=event,
                session_type=session_type,
                driver=driver,
                target_driver=scenario_target,
                gap_override_seconds=spec.get("gap_override_seconds"),
            )
        )
    return outcomes
