from typing import Literal

from pydantic import BaseModel, Field


class TelemetryQueryRequest(BaseModel):
    year: int = Field(..., ge=2018, le=2100)
    event: str = Field(..., min_length=2, max_length=120)
    session_type: Literal["FP1", "FP2", "FP3", "Q", "R", "S", "SQ"]
    driver: str = Field(..., min_length=3, max_length=3, description="Driver code, e.g. HAM")


class TelemetryChannelStats(BaseModel):
    min: float
    max: float
    avg: float
    unit: str
    series: list[float] = Field(
        default_factory=list,
        description="Downsampled channel values along the lap (≤200 points).",
    )


class TelemetrySummary(BaseModel):
    driver: str
    year: int
    event: str
    session_type: str
    sample_points: int
    speed: TelemetryChannelStats
    gear: TelemetryChannelStats
    rpm: TelemetryChannelStats
    throttle: TelemetryChannelStats | None = None
    brake: TelemetryChannelStats | None = None
    source: str = "fastf1"
    fallback: bool = False
    fallback_reason: str | None = None


class ApiError(BaseModel):
    code: str
    message: str


class TelemetryResponse(BaseModel):
    status: Literal["success", "error"]
    data: TelemetrySummary | None = None
    error: ApiError | None = None
