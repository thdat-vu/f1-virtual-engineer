"""Schemas for the /strategy/compare scenario what-if endpoint (#202).

The endpoint runs the existing ``strategy_analyzer`` once per scenario and
returns a side-by-side outcome list. Each scenario carries its own gap
override and/or target driver — the two knobs the helper actually models
today. ``target_lap`` and ``compound`` are deferred to a future helper
extension; modelling them here would be a black-box claim because the
underlying degradation predictor doesn't accept those overrides yet.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.knowledge import KnowledgeCitation


class ScenarioSpec(BaseModel):
    label: str = Field(
        ...,
        min_length=2,
        max_length=80,
        description=(
            "Human-readable scenario label. Drives both the UI header and the "
            "BM25 query for the per-scenario citation lookup, so prefer concise "
            "concept names like 'Undercut now' or 'Hold + soft' over long prose."
        ),
    )
    gap_override_seconds: float | None = Field(
        default=None,
        ge=0.0,
        le=60.0,
        description=(
            "Override the resolved gap to the rival in seconds. Use to model "
            "'what if the gap shrinks to 0.8s before we pit' versus the live "
            "FastF1 measurement. Omit to use the helper's default resolution."
        ),
    )
    target_driver: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description=(
            "Optional 3-letter rival code for the gap measurement. Mirrors "
            "AnalyzeRequest.target_driver and lets a scenario compare 'undercut "
            "to VER' vs 'undercut to LEC' from the same base context."
        ),
    )


class StrategyCompareRequest(BaseModel):
    year: int = Field(..., ge=2018, le=2100)
    event: str = Field(..., min_length=2, max_length=120)
    session_type: Literal["FP1", "FP2", "FP3", "Q", "R", "S", "SQ"]
    driver: str = Field(..., min_length=3, max_length=3)
    target_driver: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description=(
            "Default rival used when a scenario omits its own target_driver. "
            "Falls back to the car directly ahead when both are unset."
        ),
    )
    scenarios: list[ScenarioSpec] = Field(
        ...,
        min_length=1,
        max_length=3,
        description=(
            "1-3 scenario specs. Hard-cap of 3 keeps the response readable in a "
            "side-by-side card layout and bounds helper invocations per request."
        ),
    )


class ScenarioOutcome(BaseModel):
    label: str
    recommended_pit_window_laps: list[int] = Field(default_factory=list)
    confidence_band: str = "low"
    undercut_risk: str = "unknown"
    overcut_risk: str = "unknown"
    expected_gain_seconds: float | None = None
    undercut_break_even_laps: int | None = None
    current_gap_seconds: float | None = None
    gap_source: Literal["fastf1", "fallback", "explicit"] | None = None
    citations: list[KnowledgeCitation] = Field(default_factory=list)
    fallback: bool = False
    fallback_reason: str | None = None


class StrategyCompareResponse(BaseModel):
    status: Literal["success", "error"]
    scenarios: list[ScenarioOutcome] = Field(default_factory=list)
    error: str | None = None
