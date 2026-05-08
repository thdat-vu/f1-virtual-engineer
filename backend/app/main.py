import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.race_engineer import analyze_query
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.schemas.schedule import ScheduleResponse
from app.schemas.telemetry import ApiError, TelemetryQueryRequest, TelemetryResponse, TelemetrySummary
from tools.fastf1_helper import get_session_telemetry_summary, get_year_schedule

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


@app.get(
    "/",
    tags=["system"],
    summary="Service welcome endpoint",
    description="Simple discovery endpoint confirming the backend API is running.",
)
async def root():
    return {"message": "Welcome to Apex-Intelligence Virtual Race Engineer API"}


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
async def analyze_race_data(request: AnalyzeRequest):
    session_override = request.session_info.model_dump() if request.session_info else None
    result = analyze_query(
        request.query,
        session_override=session_override,
        driver_override=request.driver,
    )
    return {
        "status": "error" if result.get("error") else "success",
        "agent_response": result["response_text"],
        "query": request.query,
        "intent": result["intent"],
        "telemetry_data": result["telemetry_data"],
        "strategy_data": result.get("strategy_data"),
        "error": result["error"],
        "memory": result.get("memory"),
        "execution": result.get("execution"),
        "retry": result.get("retry"),
    }


@app.post(
    "/telemetry",
    response_model=TelemetryResponse,
    tags=["telemetry"],
    summary="Fetch normalized telemetry summary",
    description=(
        "Returns speed, gear, RPM, and fallback metadata for a concrete driver/session query using the strict telemetry contract."
    ),
)
async def get_telemetry(request: TelemetryQueryRequest):
    telemetry = get_session_telemetry_summary(
        year=request.year,
        event=request.event,
        session_type=request.session_type,
        driver=request.driver,
    )
    summary = TelemetrySummary(**telemetry)
    if summary.fallback:
        return TelemetryResponse(
            status="error",
            data=summary,
            error=ApiError(code="TELEMETRY_UNAVAILABLE", message=summary.fallback_reason or "Telemetry unavailable."),
        )
    return TelemetryResponse(status="success", data=summary, error=None)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
