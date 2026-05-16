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
    error: str | None = None
    memory: AnalyzeMemory | None = None
    execution: AnalyzeExecution | None = None
    retry: AnalyzeRetry | None = None
    citations: list[KnowledgeCitation] = Field(
        default_factory=list,
        description="FIA regulation citations retrieved for the query; empty when the query is telemetry-only or no entries matched.",
    )
