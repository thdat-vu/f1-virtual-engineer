from typing import Literal

from pydantic import BaseModel, Field


class WeatherSummaryRequest(BaseModel):
    """Per-session weather query (#235)."""

    year: int = Field(..., ge=2018, le=2100)
    event: str = Field(..., min_length=2, max_length=120)
    session_type: str = Field(..., min_length=1, max_length=4)


class WeatherSummaryResponse(BaseModel):
    status: Literal["success", "error"]
    condition: Literal["DRY", "MIXED", "WET"] | None = None
    air_temp_c: float | None = None
    track_temp_c: float | None = Field(
        default=None,
        description="Mean track surface temperature in °C. Drives tyre warm-up "
        "and degradation more than air temp.",
    )
    rainfall_fraction: float | None = Field(
        default=None,
        description="Fraction of weather samples reporting rain, 0.0-1.0. "
        "Used to derive `condition` (>=30% → WET, >0 → MIXED, =0 → DRY).",
    )
    humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    fallback: bool = False
    fallback_reason: str | None = None
