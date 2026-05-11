import asyncio
import logging
import os
from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from agents.race_engineer import analyze_query
from agents.radio_interpreter import interpret_radio
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.schemas.history import AnalyzeHistoryResponse, TelemetryHistoryResponse
from app.schemas.radio import RadioRequest, RadioResponse
from app.schemas.schedule import LapListResponse, RosterResponse, ScheduleResponse
from app.schemas.telemetry import ApiError, TelemetryQueryRequest, TelemetryResponse, TelemetrySummary
from core.auth import get_optional_user_id, get_required_user_id
from core.persistence import (
    insert_analyze_history,
    insert_telemetry_history,
    list_analyze_history,
    list_telemetry_history,
)
from core.timing import TimingMiddleware, snapshot_metrics
from tools.fastf1_helper import (
    get_event_drivers,
    get_session_lap_list,
    get_session_telemetry_summary,
    get_year_schedule,
)


_logger = logging.getLogger(__name__)


limiter = Limiter(key_func=get_remote_address, headers_enabled=False)


def _retry_after_seconds(exc: RateLimitExceeded) -> int:
    item = getattr(getattr(exc, "limit", None), "limit", None)
    if item is None:
        return 10
    return int(item.GRANULARITY.seconds * item.multiples)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = _retry_after_seconds(exc)
    body = {
        "status": "error",
        "error": {
            "code": "rate_limited",
            "message": f"Rate limit exceeded: {exc.detail}. Retry in {retry_after}s.",
            "retry_after_seconds": retry_after,
        },
    }
    response = JSONResponse(status_code=429, content=body)
    response.headers["Retry-After"] = str(retry_after)
    return response

app = FastAPI(
    title="Apex-Intelligence: Virtual Race Engineer API",
    summary="Telemetry-backed F1 strategy assistant API for mission-control and demo workflows.",
    description=(
        "FastAPI service for telemetry lookups, baseline strategy recommendations, and explainable "
        "response envelopes used by the frontend mission-control experience."
    ),
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    contact={"name": "Apex-Intelligence", "url": "https://github.com/thdat-vu/f1-virtual-engineer"},
    openapi_tags=[
        {"name": "system", "description": "Basic service discovery and health-style endpoints."},
        {"name": "analysis", "description": "Telemetry and strategy analysis workflows for the mission-control UI."},
        {"name": "telemetry", "description": "Strict telemetry contract endpoints backed by FastF1 summaries."},
    ],
)

# CORS configuration
allowed_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
if allowed_origins_str:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    # Safe defaults for local development
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

print(f"INFO: CORS enabled for origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Timing instrumentation must wrap *inside* CORS so the X-Process-Time header
# survives the CORS layer. Starlette executes middlewares in reverse order of
# registration, so registering TimingMiddleware *after* CORSMiddleware puts
# it closer to the route handler.
app.add_middleware(TimingMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


@app.get(
    "/",
    tags=["system"],
    summary="Service welcome endpoint",
    description="Simple discovery endpoint confirming the backend API is running.",
)
async def root():
    return {"message": "Welcome to Apex-Intelligence Virtual Race Engineer API"}


@app.get(
    "/metrics",
    tags=["system"],
    summary="Per-route timing snapshot",
    description=(
        "Returns rolling-window timing stats (last 50 samples per route) collected by "
        "`TimingMiddleware`. Counts, p50/p95/max in milliseconds, plus the most recent "
        "sample. Single-process, in-memory only — fine for the MVP, not for production "
        "scale. Set `METRICS_ENABLED=false` to disable both header and collection."
    ),
)
async def get_metrics():
    return {"routes": snapshot_metrics()}


@app.get(
    "/events/{year}",
    response_model=ScheduleResponse,
    tags=["telemetry"],
    summary="Fetch race schedule for a specific year",
    description="Returns a list of all Grand Prix events for the requested year.",
)
async def get_schedule(year: int):
    events = get_year_schedule(year)
    if not events:
        return ScheduleResponse(
            year=year,
            events=[],
            status="error",
            error=f"No schedule found for year {year}."
        )
    return ScheduleResponse(year=year, events=events, status="success")


@app.get(
    "/events/{year}/{event}/drivers",
    response_model=RosterResponse,
    tags=["telemetry"],
    summary="Fetch the driver roster for an event",
    description=(
        "Returns 3-letter driver codes that participated in the requested event. "
        "Tries the Race session first, then Qualifying. Returns an empty list with a "
        "fallback reason if neither session yields data (e.g. event hasn't run yet)."
    ),
)
async def get_event_roster(year: int, event: str):
    roster = get_event_drivers(year=year, event=event)
    return RosterResponse(
        year=roster["year"],
        event=roster["event"],
        drivers=roster["drivers"],
        source_session=roster.get("source_session"),
        fallback=roster["fallback"],
        fallback_reason=roster.get("fallback_reason"),
        status="error" if roster["fallback"] else "success",
        error=roster.get("fallback_reason") if roster["fallback"] else None,
    )


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    tags=["analysis"],
    summary="Analyze a telemetry or strategy question",
    description=(
        "Accepts a natural-language query plus optional explicit session context and returns either a telemetry summary "
        "or a baseline strategy recommendation with confidence, assumptions, and rationale."
    ),
)
@limiter.limit("3/10seconds")
async def analyze_race_data(
    request: Request,
    body: AnalyzeRequest,
    user_id: str | None = Depends(get_optional_user_id),
):
    session_override = body.session_info.model_dump() if body.session_info else None
    result = analyze_query(
        body.query,
        session_override=session_override,
        driver_override=body.driver,
    )

    if user_id and not result.get("error"):
        intent = result.get("intent") or {}
        # Fire-and-forget so a slow/failing PostgREST call never blocks the
        # /analyze response. The persistence helper is itself fail-closed.
        asyncio.create_task(
            insert_analyze_history(
                user_id=user_id,
                query=body.query,
                driver=intent.get("driver") or body.driver,
                event=intent.get("event") or (body.session_info.event if body.session_info else None),
                year=intent.get("year") or (body.session_info.year if body.session_info else None),
                session_type=intent.get("session_type")
                    or (body.session_info.session_type if body.session_info else None),
                agent_response=result["response_text"],
                rationale_source=result.get("rationale_source", "template"),
                intent_type=intent.get("intent_type"),
            )
        )

    return {
        "status": "error" if result.get("error") else "success",
        "agent_response": result["response_text"],
        "query": body.query,
        "intent": result["intent"],
        "telemetry_data": result["telemetry_data"],
        "strategy_data": result.get("strategy_data"),
        "rationale_source": result.get("rationale_source", "template"),
        "error": result["error"],
        "memory": result.get("memory"),
        "execution": result.get("execution"),
        "retry": result.get("retry"),
    }


@app.get(
    "/analyze/history",
    response_model=AnalyzeHistoryResponse,
    tags=["analysis"],
    summary="List the signed-in user's recent /analyze queries",
    description=(
        "Returns the most recent analyze queries for the authenticated user, ordered "
        "newest-first. Requires a valid Supabase JWT — anonymous callers receive 401."
    ),
)
async def get_analyze_history(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    user_id: str = Depends(get_required_user_id),
):
    try:
        items = await list_analyze_history(user_id=user_id, limit=limit)
    except Exception:  # noqa: BLE001
        _logger.warning("Failed to load analyze history", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": {
                    "code": "history_unavailable",
                    "message": "History service is temporarily unavailable.",
                },
            },
        )
    return {"items": items}


@app.post(
    "/radio/analyze",
    response_model=RadioResponse,
    tags=["analysis"],
    summary="Classify a team-radio transcript",
    description=(
        "Tags an F1 team-radio transcript with a single issue category, severity band, "
        "and the verbatim trigger phrase. Falls back to a 'none' classification with "
        "fallback metadata when the LLM is unavailable or returns malformed output."
    ),
)
@limiter.limit("3/10seconds")
async def analyze_radio(request: Request, body: RadioRequest):
    result = interpret_radio(transcript=body.transcript, driver=body.driver)
    return RadioResponse(
        status="error" if result["fallback"] else "success",
        classification=result["classification"],
        severity=result["severity"],
        trigger_phrase=result["trigger_phrase"],
        fallback=result["fallback"],
        fallback_reason=result.get("fallback_reason"),
    )


@app.get(
    "/laps/{year}/{event}/{session_type}/{driver}",
    response_model=LapListResponse,
    tags=["telemetry"],
    summary="Fetch the lap list for a driver in a session",
    description=(
        "Returns lap-by-lap metadata (lap number, lap time, compound, pit flags) "
        "for the requested driver/session, used by the lap-selector UI."
    ),
)
@limiter.limit("30/10seconds")
async def get_session_laps(request: Request, year: int, event: str, session_type: str, driver: str):
    data = get_session_lap_list(
        year=year,
        event=event,
        session_type=session_type,
        driver=driver,
    )
    return LapListResponse(
        year=data["year"],
        event=data["event"],
        session_type=data["session_type"],
        driver=data["driver"],
        laps=data["laps"],
        fastest_lap_number=data.get("fastest_lap_number"),
        fallback=data["fallback"],
        fallback_reason=data.get("fallback_reason"),
        status="error" if data["fallback"] else "success",
        error=data.get("fallback_reason") if data["fallback"] else None,
    )


@app.post(
    "/telemetry",
    response_model=TelemetryResponse,
    tags=["telemetry"],
    summary="Fetch normalized telemetry summary",
    description=(
        "Returns speed, gear, RPM, and fallback metadata for a concrete driver/session query using the strict telemetry contract. "
        "When `lap_number` is omitted the fastest lap is used."
    ),
)
@limiter.limit("30/10seconds")
async def get_telemetry(
    request: Request,
    body: TelemetryQueryRequest,
    user_id: str | None = Depends(get_optional_user_id),
):
    telemetry = get_session_telemetry_summary(
        year=body.year,
        event=body.event,
        session_type=body.session_type,
        driver=body.driver,
        lap_number=body.lap_number,
    )
    summary = TelemetrySummary(**telemetry)
    if summary.fallback:
        return TelemetryResponse(
            status="error",
            data=summary,
            error=ApiError(code="TELEMETRY_UNAVAILABLE", message=summary.fallback_reason or "Telemetry unavailable."),
        )

    if user_id:
        # Fire-and-forget so a slow PostgREST call never blocks the response.
        # The persistence helper is itself fail-closed.
        asyncio.create_task(
            insert_telemetry_history(
                user_id=user_id,
                year=body.year,
                event=body.event,
                session_type=body.session_type,
                driver=body.driver,
                lap_number=body.lap_number,
            )
        )

    return TelemetryResponse(status="success", data=summary, error=None)


@app.get(
    "/telemetry/history",
    response_model=TelemetryHistoryResponse,
    tags=["telemetry"],
    summary="List the signed-in user's recent /telemetry lookups",
    description=(
        "Returns the most recent telemetry lookups for the authenticated user, ordered "
        "newest-first. Requires a valid Supabase JWT — anonymous callers receive 401."
    ),
)
async def get_telemetry_history(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    user_id: str = Depends(get_required_user_id),
):
    try:
        items = await list_telemetry_history(user_id=user_id, limit=limit)
    except Exception:  # noqa: BLE001
        _logger.warning("Failed to load telemetry history", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": {
                    "code": "history_unavailable",
                    "message": "History service is temporarily unavailable.",
                },
            },
        )
    return {"items": items}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
