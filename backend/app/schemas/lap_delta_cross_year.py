from pydantic import BaseModel, Field


class LapDeltaCrossYearRequest(BaseModel):
    """Cross-year lap-delta request (#229).

    Compares the SAME driver's fastest lap across two seasons at the
    same event. Distinct from `LapDeltaRequest` which compares two
    drivers within one session.
    """

    event: str = Field(..., min_length=2, max_length=120)
    session_type: str = Field(..., min_length=1, max_length=4)
    driver: str = Field(..., min_length=3, max_length=3)
    year_a: int = Field(..., ge=2018, le=2100, description="Reference year (older car).")
    year_b: int = Field(..., ge=2018, le=2100, description="Comparison year (newer car).")


class LapDeltaCrossYearResponse(BaseModel):
    status: str
    distance_m: list[float] = Field(
        default_factory=list,
        description="Distance grid in metres. Same length as delta_seconds.",
    )
    delta_seconds: list[float] = Field(
        default_factory=list,
        description=(
            "Δt of year_b vs year_a, sampled along distance_m. Positive ⇒ "
            "year_b was slower at that distance; the older car was faster there."
        ),
    )
    driver: str | None = None
    year_a: int | None = None
    year_b: int | None = None
    lap_a: int | None = None
    lap_b: int | None = None
    lap_time_a_seconds: float | None = Field(
        default=None,
        description="Driver's fastest lap time in year_a, seconds. Null if unavailable.",
    )
    lap_time_b_seconds: float | None = Field(
        default=None,
        description="Driver's fastest lap time in year_b, seconds. Null if unavailable.",
    )
    fallback: bool = False
    fallback_reason: str | None = None
