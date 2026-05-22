from pydantic import BaseModel, Field


class LapDeltaRequest(BaseModel):
    year: int = Field(..., ge=2018, le=2100)
    event: str = Field(..., min_length=2, max_length=120)
    session_type: str = Field(..., min_length=1, max_length=4)
    reference_driver: str = Field(..., min_length=3, max_length=3)
    compare_driver: str = Field(..., min_length=3, max_length=3)
    reference_lap: int | None = Field(default=None, ge=1, le=200)
    compare_lap: int | None = Field(default=None, ge=1, le=200)


class LapDeltaResponse(BaseModel):
    status: str
    distance_m: list[float] = Field(
        default_factory=list,
        description="Distance grid (metres). Same length as delta_seconds.",
    )
    delta_seconds: list[float] = Field(
        default_factory=list,
        description=(
            "Compare-driver Δt vs reference driver, sampled along distance_m. "
            "Positive ⇒ compare was behind at that point on the lap."
        ),
    )
    reference_driver: str | None = None
    compare_driver: str | None = None
    reference_lap: int | None = None
    compare_lap: int | None = None
    fallback: bool = False
    fallback_reason: str | None = None
