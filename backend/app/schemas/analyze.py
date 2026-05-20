from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.knowledge import KnowledgeCitation
from app.schemas.telemetry import TelemetrySummary


class AnalyzeSessionInfo(BaseModel):
    event: str = Field(..., min_length=2, max_length=120, description="Grand Prix or event name, e.g. Japanese Grand Prix")
    year: int = Field(..., ge=2018, le=2100, description="Championship season year")
    session_type: Literal["FP1", "FP2", "FP3", "Q", "R", "S", "SQ"] = Field(
        ...,
        description="FastF1 session token",
    )


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Natural language telemetry or strategy question")
    driver: str | None = Field(default=None, min_length=3, max_length=3, description="Optional 3-letter driver code")
    session_info: AnalyzeSessionInfo | None = Field(
        default=None,
        description="Optional explicit session context to align frontend and backend assumptions",
    )
    target_driver: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description=(
            "Optional 3-letter code of the competitor to measure gap against. "
            "When omitted the strategy analyzer uses the car directly ahead. "
            "Slice 1B of #168."
        ),
    )


class StrategySummary(BaseModel):
    recommended_pit_window_laps: list[int]
    target_lap: int | None = Field(default=None, description="The specific lap recommended for the pit stop")
    undercut_risk: str
    overcut_risk: str
    confidence_band: str
    assumptions: list[str]
    rationale: list[str]
    fallback: bool = False
    fallback_reason: str | None = None
    current_gap_seconds: float | None = Field(
        default=None,
        description="Gap (s) to the car ahead at the sampled lap, or the fallback assumption when FastF1 lookup failed.",
    )
    gap_source: Literal["fastf1", "fallback", "explicit"] | None = Field(
        default=None,
        description="Where current_gap_seconds came from: live FastF1, hardcoded fallback, or an explicit caller override.",
    )
    competitor_ahead: str | None = Field(
        default=None,
        description="3-letter code of the driver the gap was measured against (car directly ahead by default, or the user-picked target).",
    )
    competitor_position_relative: Literal["ahead", "behind"] | None = Field(
        default=None,
        description="Where the picked competitor sits relative to driver. Always 'ahead' when no target was specified.",
    )
    gap_sampled_at_lap: int | None = Field(
        default=None,
        description="Lap number at which the gap was sampled.",
    )


class AnalyzeIntent(BaseModel):
    intent: str | None = None
    intent_type: Literal["telemetry", "strategy"] | None = None
    driver: str | None = None
    driver_candidates: list[str] = []
    year: int | None = None
    event: str | None = None
    session_type: str | None = None
    needs_clarification: bool = False
    clarification_message: str | None = None


class AnalyzeMemory(BaseModel):
    history_size: int
    retention_cap: int
    last_driver: str | None = None


class TraceEntry(BaseModel):
    tool: str
    duration_ms: float
    status: Literal["ok", "error"] = "ok"


class AnalyzeExecution(BaseModel):
    step_limit: int
    duration_limit_seconds: float
    duration_ms: float
    termination_reason: str
    trace: list[TraceEntry] = Field(default_factory=list)


class AnalyzeRetry(BaseModel):
    count: int
    max_retries: int
    retryable_exhausted: bool
    retry_backoff_seconds: float | None = None


class AnalyzeResponse(BaseModel):
    status: Literal["success", "error"]
    agent_response: str
    query: str
    intent: AnalyzeIntent
    telemetry_data: TelemetrySummary | dict = {}
    strategy_data: StrategySummary | None = None
    rationale_source: Literal["llm", "template"] = Field(
        default="template",
        description="Whether `agent_response` came from the Gemini LLM path or the deterministic template fallback.",
    )
    rationale_job_id: str | None = Field(
        default=None,
        description=(
            "Set only when `RATIONALE_ASYNC=true` and a worker has been queued to back-fill an LLM rationale onto the persisted history row. "
            "Frontends can poll `/analyze/history` and watch for the row's `rationale_source` to flip from `template` to `llm`."
        ),
    )
    analyze_history_id: str | None = Field(
        default=None,
        description=(
            "ID of the persisted `analyze_history` row, populated when the caller is signed in and persistence succeeded. "
            "Frontends use this to track the matching row in `/analyze/history` while waiting for the async rationale upgrade."
        ),
    )
    error: str | None = None
    memory: AnalyzeMemory | None = None
    execution: AnalyzeExecution | None = None
    retry: AnalyzeRetry | None = None
    citations: list[KnowledgeCitation] = Field(
        default_factory=list,
        description="FIA regulation citations retrieved for the query; empty when the query is telemetry-only or no entries matched.",
    )
