from typing import Literal

from pydantic import BaseModel, Field


class TyreAnalyzeRequest(BaseModel):
    """Request shape for ``POST /tyre/analyze`` (#167)."""

    year: int = Field(..., ge=2018, le=2100)
    event: str = Field(..., min_length=2, max_length=120)
    session_type: Literal["FP1", "FP2", "FP3", "Q", "R", "S", "SQ"]
    driver: str = Field(..., min_length=3, max_length=3, description="Driver code, e.g. HAM")


class TyreAnalyzeResponse(BaseModel):
    """Tyre intelligence snapshot — see ``tools.tyre_helper.compute_tyre_decay``."""

    status: Literal["success", "error"]
    driver: str
    year: int
    event: str
    session_type: str
    compound: str | None = Field(
        default=None,
        description="Current stint compound (e.g. SOFT). Null on fallback or roster outage.",
    )
    stint_laps: int = Field(
        default=0, ge=0,
        description="Laps completed in the current stint (post last pit).",
    )
    decay_seconds_per_lap: float = Field(
        default=0.0, ge=0.0,
        description="Observed lap-time slope. Higher = closer to the cliff.",
    )
    cliff_lap_estimate: int | None = Field(
        default=None,
        description="Projected stint-relative lap where pace drops; null when uncertain.",
    )
    confidence_band: Literal["high", "medium", "low"] = "low"
    fallback: bool = False
    fallback_reason: str | None = None
