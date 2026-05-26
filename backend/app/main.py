import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from agents.race_engineer import analyze_query
from agents.radio_interpreter import interpret_radio
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.schemas.history import AnalyzeHistoryResponse, RadioHistoryResponse, TelemetryHistoryResponse
from app.schemas.radio import RadioRequest, RadioResponse
from app.schemas.saved_queries import (
    SavedQueryCreateRequest,
    SavedQueryItem,
    SavedQueryListResponse,
)
from app.schemas.knowledge import (
    KnowledgeLookupRequest,
    KnowledgeLookupResponse,
    KnowledgeNoteResponse,
)
from app.schemas.strategy_compare import StrategyCompareRequest, StrategyCompareResponse
from app.schemas.lap_delta import LapDeltaRequest, LapDeltaResponse
from app.schemas.lap_delta_cross_year import (
    LapDeltaCrossYearRequest,
    LapDeltaCrossYearResponse,
)
from app.schemas.schedule import LapListResponse, RosterResponse, ScheduleResponse
from app.schemas.telemetry import ApiError, TelemetryQueryRequest, TelemetryResponse, TelemetrySummary
from app.schemas.tyre import TyreAnalyzeRequest, TyreAnalyzeResponse
from app.schemas.weather import WeatherSummaryRequest, WeatherSummaryResponse
from core.auth import get_optional_user_id, get_required_user_id
from core.persistence import (
    delete_saved_query,
    insert_analyze_history,
    insert_radio_history,
    insert_saved_query,
    insert_telemetry_history,
    list_analyze_history,
    list_radio_history,
    list_saved_queries,
    list_telemetry_history,
)
from core.timing import TimingMiddleware, snapshot_metrics
from core import redis_cache
from core import idempotency
from core.rabbitmq_metrics import snapshot_worker_metrics
from tools.fastf1_helper import (
    get_event_drivers,
    get_session_lap_list,
    get_session_telemetry_summary,
    get_year_schedule,
    load_prebaked_into_caches,
)
from tools.knowledge_retriever import get_note as knowledge_get_note, lookup as knowledge_lookup
from tools.lap_delta import compute_lap_delta
from tools.lap_delta_cross_year import compute_cross_year_lap_delta
from tools.strategy_compare import compare_scenarios as compare_strategy_scenarios
from tools.tyre_helper import compute_tyre_decay
from tools.weather_helper import get_weather_summary


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

@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Warm the FastF1 helper caches from any pre-baked snapshots on disk
    # (slice C of #100). The load is best-effort: a missing/empty prebake
    # dir is fine, and a corrupt file is logged & skipped rather than
    # crashing startup.
    try:
        loaded = await asyncio.to_thread(load_prebaked_into_caches)
        if loaded:
            _logger.info("Loaded %d pre-baked FastF1 entries into cache", loaded)
    except Exception:  # noqa: BLE001
        _logger.warning("Prebake warmup failed", exc_info=True)
    yield


app = FastAPI(
    lifespan=_lifespan,
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
        {"name": "knowledge", "description": "FIA regulation retrieval for citation-backed answers."},
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
    return {
        "routes": snapshot_metrics(),
        "cache": {"redis_enabled": redis_cache.is_enabled()},
        "workers": await _snapshot_workers(),
    }


async def _snapshot_workers() -> dict[str, int | bool]:
    """Combine 24h Celery counters with live broker queue stats (#139).

    Two sources of truth, fail-closed at each layer:

    1. **Redis counters** (``workers:completed_24h`` / ``workers:failed_24h``) —
       bumped by the worker on terminal failure / task success. 24h TTL
       set on first increment so the snapshot reflects a moving window
       without us having to schedule a sweeper.

    2. **RabbitMQ Management API** — live queue depth, in-flight, and
       DLQ size. The broker is the authoritative source even when the
       worker pool is down (which is exactly when queue_depth is most
       interesting to see).

    Either source unreachable degrades to zeros for that block plus a
    boolean flag (``redis_enabled`` / ``broker_reachable``). ``/metrics``
    itself must never 5xx because of an observability dependency.
    """
    snapshot: dict[str, int | bool] = {
        "completed_24h": 0,
        "failed_24h": 0,
        "redis_enabled": redis_cache.is_enabled(),
        "queue_depth": 0,
        "in_flight": 0,
        "dlq_size": 0,
        "broker_reachable": False,
    }
    if snapshot["redis_enabled"]:
        try:
            client = redis_cache._get_client()
            if client is not None:
                for key, label in (
                    ("workers:completed_24h", "completed_24h"),
                    ("workers:failed_24h", "failed_24h"),
                ):
                    raw = client.get(key)
                    if raw is None:
                        continue
                    try:
                        snapshot[label] = int(raw)
                    except (TypeError, ValueError):
                        continue
        except Exception:  # noqa: BLE001 — fail-closed
            _logger.warning("Failed to read worker counters from Redis", exc_info=True)

    try:
        broker_stats = await snapshot_worker_metrics()
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Failed to read worker queue stats from RabbitMQ", exc_info=True)
    else:
        snapshot.update(broker_stats)

    return snapshot


@app.get(
    "/events/{year}",
    response_model=ScheduleResponse,
    tags=["telemetry"],
    summary="Fetch race schedule for a specific year",
    description="Returns a list of all Grand Prix events for the requested year.",
)
async def get_schedule(year: int):
    events = await asyncio.to_thread(get_year_schedule, year)
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
    roster = await asyncio.to_thread(get_event_drivers, year=year, event=event)
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
        "or a baseline strategy recommendation with confidence, assumptions, and rationale.\n\n"
        "Pass an optional `Idempotency-Key` header (UUID recommended) to dedupe retries. The server caches the response "
        "for 60s under that key — duplicate POSTs within the window return the cached payload without re-running the agent "
        "or writing a second history row. Concurrent requests with the same key get HTTP 409 with a `Retry-After: 2` hint."
    ),
)
@limiter.limit("3/10seconds")
async def analyze_race_data(
    request: Request,
    body: AnalyzeRequest,
    user_id: str | None = Depends(get_optional_user_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    # Idempotency dedupe (#161 / #159 Layer 2). When the client sends an
    # Idempotency-Key, short-circuit duplicate POSTs so:
    #   1. Network retries don't double-write analyze_history rows.
    #   2. Network retries don't burn duplicate Gemini quota.
    #   3. Two browser tabs hammering Analyze at the same instant don't
    #      both run the agent — the second one sees the pending entry.
    # Fail-open: a Redis blip skips dedupe and the request runs as if
    # the header weren't there. /analyze must never 5xx because the
    # idempotency layer is unhealthy.
    if idempotency_key:
        cached = idempotency.lookup(idempotency_key)
        if cached is not None:
            status, payload = cached
            if status == idempotency.STATUS_DONE and payload is not None:
                return payload
            if status == idempotency.STATUS_PENDING:
                return JSONResponse(
                    status_code=409,
                    headers={"Retry-After": "2"},
                    content={"error": "Duplicate request in flight; retry shortly."},
                )
        # First writer wins: if reserve() returns False another caller
        # already claimed this key in the gap between lookup() and now.
        if not idempotency.reserve(idempotency_key):
            return JSONResponse(
                status_code=409,
                headers={"Retry-After": "2"},
                content={"error": "Duplicate request in flight; retry shortly."},
            )

    try:
        # Async-rationale path is opt-in (#139 PR3). It only triggers when:
        #   1. The env flag is on, AND
        #   2. The caller is authenticated (we need a persisted row to back-fill)
        # Anonymous callers always get the synchronous LLM path so they don't
        # see a degraded "template-only" response with no upgrade route.
        rationale_async = (
            os.environ.get("RATIONALE_ASYNC", "").strip().lower() in {"1", "true", "yes", "on"}
            and user_id is not None
        )

        session_override = body.session_info.model_dump() if body.session_info else None
        result = await asyncio.to_thread(
            analyze_query,
            body.query,
            session_override=session_override,
            driver_override=body.driver,
            target_driver=body.target_driver,
            force_template=rationale_async,
        )

        rationale_job_id: str | None = None
        analyze_history_id: str | None = None
        if user_id and not result.get("error"):
            intent = result.get("intent") or {}
            if rationale_async:
                # Synchronous insert: we need the row id to hand to the worker.
                # The fail-closed helper still won't raise — it returns None on
                # outage and we just skip the enqueue.
                row_id = await insert_analyze_history(
                    user_id=user_id,
                    query=body.query,
                    driver=intent.get("driver") or body.driver,
                    event=intent.get("event") or (body.session_info.event if body.session_info else None),
                    year=intent.get("year") or (body.session_info.year if body.session_info else None),
                    session_type=intent.get("session_type")
                        or (body.session_info.session_type if body.session_info else None),
                    agent_response=result["response_text"],
                    rationale_source="template",
                    intent_type=intent.get("intent_type"),
                )
                analyze_history_id = row_id
                if row_id:
                    try:
                        # Local import: keeps tasks/* off the import path of any
                        # caller that doesn't run the async path (and makes it
                        # cheap to monkeypatch in tests).
                        from tasks.rationale import backfill_rationale

                        llm_context = {
                            "intent": intent,
                            "telemetry_data": result.get("telemetry_data") or {},
                            "strategy_data": result.get("strategy_data") or {},
                            "citations": [
                                {k: v for k, v in c.items() if k != "score"}
                                for c in (result.get("citations") or [])
                            ],
                        }
                        async_result = backfill_rationale.delay(
                            row_id=row_id,
                            user_id=user_id,
                            llm_context=llm_context,
                        )
                        rationale_job_id = async_result.id
                    except Exception:  # noqa: BLE001
                        # A broker outage must never break /analyze. We still
                        # have the row persisted with rationale_source='template';
                        # the upgrade just won't happen this time.
                        _logger.warning("Failed to enqueue rationale backfill", exc_info=True)
            else:
                # Fire-and-forget so a slow/failing PostgREST call never blocks
                # the /analyze response. The persistence helper is itself
                # fail-closed.
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

        response_payload = {
            "status": "error" if result.get("error") else "success",
            "agent_response": result["response_text"],
            "query": body.query,
            "intent": result["intent"],
            "telemetry_data": result["telemetry_data"],
            "strategy_data": result.get("strategy_data"),
            "rationale_source": result.get("rationale_source", "template"),
            "rationale_job_id": rationale_job_id,
            "analyze_history_id": analyze_history_id,
            "error": result["error"],
            "memory": result.get("memory"),
            "execution": result.get("execution"),
            "retry": result.get("retry"),
            "citations": result.get("citations", []),
        }
    except Exception:
        # If the agent run blew up, drop the pending key so a client
        # retry actually re-runs instead of getting 409 for 60s.
        if idempotency_key:
            idempotency.release(idempotency_key)
        raise

    if idempotency_key:
        idempotency.commit(idempotency_key, response_payload)
    return response_payload


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
async def analyze_radio(
    request: Request,
    body: RadioRequest,
    user_id: str | None = Depends(get_optional_user_id),
):
    result = interpret_radio(transcript=body.transcript, driver=body.driver)
    if user_id:
        asyncio.create_task(
            insert_radio_history(
                user_id=user_id,
                transcript=body.transcript,
                driver=body.driver,
                classification=result["classification"],
                severity=result["severity"],
                trigger_phrase=result.get("trigger_phrase"),
                fallback=result["fallback"],
            )
        )
    return RadioResponse(
        status="error" if result["fallback"] else "success",
        classification=result["classification"],
        severity=result["severity"],
        trigger_phrase=result["trigger_phrase"],
        fallback=result["fallback"],
        fallback_reason=result.get("fallback_reason"),
    )


@app.get(
    "/radio/history",
    response_model=RadioHistoryResponse,
    tags=["analysis"],
    summary="List the signed-in user's recent radio classifications",
    description=(
        "Returns the most recent radio classifications for the authenticated user, ordered "
        "newest-first. Optionally filtered by driver code. Requires a valid Supabase JWT."
    ),
)
async def get_radio_history(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    driver: str | None = Query(None, description="Filter by 3-letter driver code, e.g. VER"),
    user_id: str = Depends(get_required_user_id),
):
    try:
        items = await list_radio_history(user_id=user_id, limit=limit, driver=driver)
    except Exception:  # noqa: BLE001
        _logger.warning("Failed to load radio history", exc_info=True)
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
    data = await asyncio.to_thread(
        get_session_lap_list,
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
    telemetry = await asyncio.to_thread(
        get_session_telemetry_summary,
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


@app.post(
    "/tyre/analyze",
    response_model=TyreAnalyzeResponse,
    tags=["telemetry"],
    summary="Tyre intelligence snapshot for a driver/session",
    description=(
        "Returns the current stint compound, observed lap-time decay, and a projected "
        "cliff-lap estimate. Composes the cached lap roster with the predict_tyre_wear "
        "heuristic — fail-closed: any FastF1 hiccup degrades to a populated envelope "
        "with `fallback: true` rather than 5xx."
    ),
)
@limiter.limit("30/10seconds")
async def analyze_tyre(
    request: Request,
    body: TyreAnalyzeRequest,
):
    snapshot = await asyncio.to_thread(
        compute_tyre_decay,
        year=body.year,
        event=body.event,
        session_type=body.session_type,
        driver=body.driver,
    )
    return TyreAnalyzeResponse(
        status="error" if snapshot.get("fallback") else "success",
        **snapshot,
    )


@app.post(
    "/weather",
    response_model=WeatherSummaryResponse,
    tags=["telemetry"],
    summary="Per-session weather summary (#235)",
    description=(
        "Aggregates FastF1 `session.weather_data` into a compact envelope: "
        "condition (DRY/MIXED/WET derived from rainfall fraction), mean air + "
        "track temp, humidity, wind. Frontend uses this to render a header "
        "weather pill and to flag mismatched conditions in cross-year "
        "comparisons. Fail-closed — any FastF1 hiccup degrades to a populated "
        "envelope with `fallback: true` rather than 5xx."
    ),
)
@limiter.limit("30/10seconds")
async def weather_summary(
    request: Request,
    body: WeatherSummaryRequest,
):
    payload = await asyncio.to_thread(
        get_weather_summary,
        year=body.year,
        event=body.event,
        session_type=body.session_type,
    )
    return WeatherSummaryResponse(
        status="error" if payload.get("fallback") else "success",
        **payload,
    )


@app.post(
    "/strategy/compare",
    response_model=StrategyCompareResponse,
    tags=["analysis"],
    summary="Side-by-side what-if for 1-3 strategy scenarios",
    description=(
        "Runs `strategy_analyzer` once per scenario spec and returns one outcome "
        "per slot — recommended pit window, confidence, expected gain, plus a "
        "BM25 citation lookup using the scenario label as the query. Per-scenario "
        "fail-closed: if one slot's helper raises, the others still return and "
        "only that slot carries `fallback: true` with a reason."
    ),
)
@limiter.limit("5/10seconds")
async def compare_strategies(
    request: Request,
    body: StrategyCompareRequest,
):
    outcomes = await asyncio.to_thread(
        compare_strategy_scenarios,
        year=body.year,
        event=body.event,
        session_type=body.session_type,
        driver=body.driver,
        target_driver=body.target_driver,
        scenarios=[s.model_dump() for s in body.scenarios],
    )
    return {
        "status": "success",
        "scenarios": outcomes,
    }


@app.post(
    "/lap-delta",
    response_model=LapDeltaResponse,
    tags=["telemetry"],
    summary="Per-distance Δt between two drivers' fastest (or pinned) laps",
    description=(
        "Aligns each driver's lap telemetry on Distance and returns the "
        "compare driver's time delta to the reference driver, sampled at "
        "250 points along the lap. Positive values mean compare was behind. "
        "Fail-closed: any FastF1 hiccup degrades to a populated envelope "
        "with `fallback: true` instead of 5xx."
    ),
)
@limiter.limit("30/10seconds")
async def lap_delta(request: Request, body: LapDeltaRequest):
    payload = await asyncio.to_thread(
        compute_lap_delta,
        year=body.year,
        event=body.event,
        session_type=body.session_type,
        reference_driver=body.reference_driver,
        compare_driver=body.compare_driver,
        reference_lap=body.reference_lap,
        compare_lap=body.compare_lap,
    )
    return LapDeltaResponse(
        status="error" if payload.get("fallback") else "success",
        **payload,
    )


@app.post(
    "/lap-delta-cross-year",
    response_model=LapDeltaCrossYearResponse,
    tags=["telemetry"],
    summary="Per-distance Δt of one driver's fastest laps across two seasons",
    description=(
        "Loads two sessions (same event, different years) and aligns the "
        "driver's fastest lap from each on Distance. Δt at each metre tells "
        "the story of what changed between car generations. Positive ⇒ "
        "year_b was slower there; older car was faster on that section. "
        "Same fail-closed envelope as /lap-delta. (#229)"
    ),
)
@limiter.limit("10/10seconds")
async def lap_delta_cross_year(
    request: Request,
    body: LapDeltaCrossYearRequest,
):
    payload = await asyncio.to_thread(
        compute_cross_year_lap_delta,
        event=body.event,
        session_type=body.session_type,
        driver=body.driver,
        year_a=body.year_a,
        year_b=body.year_b,
    )
    return LapDeltaCrossYearResponse(
        status="error" if payload.get("fallback") else "success",
        **payload,
    )


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


@app.post(
    "/saved-queries",
    response_model=SavedQueryItem,
    status_code=201,
    tags=["analysis"],
    summary="Star a query so it survives past the rolling history window",
    description=(
        "Persists an analyze or telemetry request body under the signed-in user. "
        "Returns the created row so the frontend can render the star as 'already saved'."
    ),
)
async def create_saved_query(
    request: Request,
    body: SavedQueryCreateRequest,
    user_id: str = Depends(get_required_user_id),
):
    try:
        row = await insert_saved_query(
            user_id=user_id,
            kind=body.kind,
            payload=body.payload,
            label=body.label,
        )
    except Exception:  # noqa: BLE001
        _logger.warning("Failed to insert saved query", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": {
                    "code": "saved_queries_unavailable",
                    "message": "Saved queries service is temporarily unavailable.",
                },
            },
        )
    if row is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": {
                    "code": "saved_queries_unavailable",
                    "message": "Saved queries service is not configured.",
                },
            },
        )
    return row


@app.get(
    "/saved-queries",
    response_model=SavedQueryListResponse,
    tags=["analysis"],
    summary="List the signed-in user's saved queries",
)
async def get_saved_queries(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_required_user_id),
):
    try:
        items = await list_saved_queries(user_id=user_id, limit=limit)
    except Exception:  # noqa: BLE001
        _logger.warning("Failed to load saved queries", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": {
                    "code": "saved_queries_unavailable",
                    "message": "Saved queries service is temporarily unavailable.",
                },
            },
        )
    return {"items": items}


@app.delete(
    "/saved-queries/{query_id}",
    status_code=204,
    tags=["analysis"],
    summary="Delete a saved query owned by the signed-in user",
    description=(
        "Returns 204 on success. Returns 404 when the row does not exist or "
        "belongs to a different user — the latter mapped to 404 to avoid "
        "leaking id existence to non-owners."
    ),
)
async def remove_saved_query(
    request: Request,
    query_id: str,
    user_id: str = Depends(get_required_user_id),
):
    try:
        deleted = await delete_saved_query(user_id=user_id, query_id=query_id)
    except Exception:  # noqa: BLE001
        _logger.warning("Failed to delete saved query", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": {
                    "code": "saved_queries_unavailable",
                    "message": "Saved queries service is temporarily unavailable.",
                },
            },
        )
    if not deleted:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "error": {
                    "code": "not_found",
                    "message": "Saved query not found.",
                },
            },
        )
    return JSONResponse(status_code=204, content=None)


@app.post(
    "/knowledge/lookup",
    response_model=KnowledgeLookupResponse,
    tags=["knowledge"],
    summary="Retrieve FIA regulation citations for a natural-language query",
    description=(
        "Runs a BM25 lookup over the curated FIA regulation corpus and returns "
        "the top-k matching entries with title, source, section, topics, snippet, "
        "and score — ready for downstream citation rendering."
    ),
)
@limiter.limit("10/10seconds")
async def knowledge_lookup_endpoint(
    request: Request,
    body: KnowledgeLookupRequest,
):
    citations = await asyncio.to_thread(knowledge_lookup, body.query, body.k)
    return {
        "status": "success",
        "query": body.query,
        "citations": citations,
    }


@app.get(
    "/knowledge/note/{note_id}",
    response_model=KnowledgeNoteResponse,
    tags=["knowledge"],
    summary="Fetch a single corpus note by id (full body)",
    description=(
        "Returns the full untruncated body of a knowledge corpus entry. Used by the "
        "citation chip popover in Mission Control after a chip is clicked. Returns "
        "404 with a structured envelope when the id does not match any corpus entry."
    ),
)
@limiter.limit("30/10seconds")
async def knowledge_note_endpoint(
    request: Request,
    note_id: str,
):
    note = await asyncio.to_thread(knowledge_get_note, note_id)
    if note is None:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "note": None,
                "error": f"Knowledge note '{note_id}' not found.",
            },
        )
    return {"status": "success", "note": note}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
