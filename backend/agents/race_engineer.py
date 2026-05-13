import copy
import re
from collections import deque
from time import monotonic, sleep
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from core.llm import generate_rationale
from core.trace import start_trace, get_trace, traced
from tools.fastf1_helper import get_session_telemetry_summary as _raw_get_telemetry
from tools.knowledge_retriever import lookup as _raw_knowledge_lookup
from tools.strategy_helper import strategy_analyzer as _raw_strategy_analyzer

get_session_telemetry_summary = traced("telemetry")(_raw_get_telemetry)
strategy_analyzer = traced("strategy")(_raw_strategy_analyzer)
knowledge_lookup = traced("knowledge")(_raw_knowledge_lookup)

DEFAULT_EVENT = "Japanese Grand Prix"
DEFAULT_SESSION_TYPE = "R"
DEFAULT_YEAR = 2023
DRIVER_MAP = {
    "VERSTAPPEN": "VER",
    "MAX VERSTAPPEN": "VER",
    "MAX": "VER",
    "HAMILTON": "HAM",
    "LEWIS HAMILTON": "HAM",
    "LEWIS": "HAM",
    "NORRIS": "NOR",
    "LANDO NORRIS": "NOR",
    "LANDO": "NOR",
    "LECLERC": "LEC",
    "CHARLES LECLERC": "LEC",
    "CHARLES": "LEC",
    "SAINZ": "SAI",
    "CARLOS SAINZ": "SAI",
    "CARLOS": "SAI",
    "RUSSELL": "RUS",
    "GEORGE RUSSELL": "RUS",
    "GEORGE": "RUS",
    "PEREZ": "PER",
    "SERGIO PEREZ": "PER",
    "SERGIO": "PER",
    "CHECO": "PER",
    "ALONSO": "ALO",
    "FERNANDO ALONSO": "ALO",
    "FERNANDO": "ALO",
    "PIASTRI": "PIA",
    "OSCAR PIASTRI": "PIA",
    "OSCAR": "PIA",
    "OCON": "OCO",
    "ESTEBAN OCON": "OCO",
    "ESTEBAN": "OCO",
    "GASLY": "GAS",
    "PIERRE GASLY": "GAS",
    "PIERRE": "GAS",
    "TSUNODA": "TSU",
    "YUKI TSUNODA": "TSU",
    "YUKI": "TSU",
    "ALBON": "ALB",
    "ALEX ALBON": "ALB",
    "ALEX": "ALB",
    "STROLL": "STR",
    "LANCE STROLL": "STR",
    "LANCE": "STR",
    "RICCIARDO": "RIC",
    "DANIEL RICCIARDO": "RIC",
    "DANIEL": "RIC",
    "HULKENBERG": "HUL",
    "NICO HULKENBERG": "HUL",
    "NICO": "HUL",
    "MAGNUSSEN": "MAG",
    "KEVIN MAGNUSSEN": "MAG",
    "KEVIN": "MAG",
    "BOTTAS": "BOT",
    "VALTTERI BOTTAS": "BOT",
    "VALTTERI": "BOT",
    "ZHOU": "ZHO",
    "GUANYU ZHOU": "ZHO",
    "GUANYU": "ZHO",
    "SARGEANT": "SAR",
    "LOGAN SARGEANT": "SAR",
    "LOGAN": "SAR",
    "BEARMAN": "BEA",
    "OLIVER BEARMAN": "BEA",
    "OLLIE": "BEA",
}
# Sort keys by length descending to match longest possible driver name first
sorted_driver_names = sorted(DRIVER_MAP.keys(), key=len, reverse=True)
DRIVER_PATTERN = re.compile(
    r"\b("
    + "|".join(re.escape(name) for name in sorted_driver_names)
    + r"|HAM|VER|NOR|LEC|SAI|RUS|PER|ALO|PIA|OCO|GAS|TSU|ALB|STR|RIC|HUL|MAG|BOT|ZHO|SAR"
    + r")\b",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
SESSION_PATTERN = re.compile(r"\b(FP1|FP2|FP3|Q|R|S|SQ|race|qualifying)\b", re.IGNORECASE)
COMPARE_PATTERN = re.compile(r"\b(compare|versus|vs|so voi|against)\b", re.IGNORECASE)
FOLLOWUP_PATTERN = re.compile(r"\b(and|what\s+about|how\s+about|him|her|them|his|their|also|furthermore|he|she|it|again)\b", re.IGNORECASE)
STRATEGY_PATTERN = re.compile(
    r"\b(strategy|pit|pit\s+window|undercut|overcut|tyre|tire|wear|degradation|should\s+.*pit|box)\b",
    re.IGNORECASE,
)
# Queries that mention any of these deserve an FIA regulation lookup. Keep the
# list tight — matching anything fires BM25 ranking, so an over-broad pattern
# would attach citations to pure telemetry questions and dilute the signal.
KNOWLEDGE_PATTERN = re.compile(
    r"\b(drs|safety\s*car|yellow\s*flag|pit\s*lane|pit\s*speed|tyre\s*compound|tire\s*compound|"
    r"compound|regulation|rule|rules|fia|penalty|penalties|steward|stewards|flag|restart)\b",
    re.IGNORECASE,
)
DOMAIN_KEYWORDS = ("strategy", "telemetry", "pace", "data", "result", "box", "speed", "gear", "rpm", "pit", "window", "pit soon", "should he", "should she")
COMMON_WORDS = {
    "what", "about", "how", "show", "tell", "the", "and", "me", "is", "was", "were", 
    "for", "in", "of", "to", "with", "his", "her", "again", "more", "also", "please", 
    "can", "you", "it", "its", "at", "on", "from", "by", "give", "display", "check", 
    "look", "at", "for", "get", "inform", "details", "info", "information"
}
MEMORY_RETENTION_CAP = 10
MEMORY_STORE: deque[dict[str, Any]] = deque(maxlen=MEMORY_RETENTION_CAP)
MAX_GRAPH_STEPS = 6
MAX_GRAPH_DURATION_SECONDS = 15.0  # Increased timeout for complex data fetching
MAX_TOOL_RETRIES = 2
RETRY_BACKOFF_SECONDS = 0.1
RETRYABLE_ERROR_HINTS = ("timeout", "timed out", "temporarily unavailable", "connection", "rate limit")


class AgentState(TypedDict):
    query: str
    intent: dict[str, Any]
    telemetry_data: dict[str, Any]
    strategy_data: dict[str, Any]
    response_text: str
    error: str | None
    memory: dict[str, Any]
    retry_count: int
    retry_metadata: dict[str, Any]
    overrides: dict[str, Any]
    rationale_source: str  # "llm" or "template"
    citations: list[dict[str, Any]]


def parse_query_intent(query: str) -> dict[str, Any]:
    normalized = query.upper()
    raw_matches = DRIVER_PATTERN.findall(normalized)
    unique_drivers: list[str] = []
    for match in raw_matches:
        code = DRIVER_MAP.get(match.upper(), match.upper())
        if code not in unique_drivers:
            unique_drivers.append(code)

    driver_match = unique_drivers[0] if unique_drivers else None
    year_match = YEAR_PATTERN.search(normalized)
    session_match = SESSION_PATTERN.search(query)
    intent_type = "strategy" if STRATEGY_PATTERN.search(query) else "telemetry"

    intent = {
        "intent": "strategy_lookup" if intent_type == "strategy" else "telemetry_lookup",
        "intent_type": intent_type,
        "driver": driver_match,
        "driver_candidates": unique_drivers,
        "year": int(year_match.group(1)) if year_match else DEFAULT_YEAR,
        "event": DEFAULT_EVENT,
        "session_type": DEFAULT_SESSION_TYPE,
        "needs_clarification": False,
        "clarification_message": None,
    }

    if session_match:
        session_token = session_match.group(1).upper()
        intent["session_type"] = "Q" if session_token == "QUALIFYING" else ("R" if session_token == "RACE" else session_token)

    if "JAPAN" in normalized or "NHAT" in normalized:
        intent["event"] = "Japanese Grand Prix"
    elif "MONACO" in normalized:
        intent["event"] = "Monaco Grand Prix"
    elif "BRITISH" in normalized or "SILVERSTONE" in normalized:
        intent["event"] = "British Grand Prix"

    if len(unique_drivers) > 1:
        intent["needs_clarification"] = True
        intent["clarification_message"] = (
            "Multiple driver codes detected. Please specify exactly one driver for this query."
        )
    elif not unique_drivers:
        intent["needs_clarification"] = True
        intent["clarification_message"] = "Please provide a 3-letter driver code (for example: HAM, VER, NOR) or a full driver name."

    return intent


# Backward compatibility for current tests/imports
parse_telemetry_intent = parse_query_intent


def parse_intent_node(state: AgentState) -> AgentState:
    intent = parse_query_intent(state["query"])
    overrides = state.get("overrides") or {}
    if overrides:
        if overrides.get("driver"):
            intent["driver"] = overrides["driver"].upper()
            intent["driver_candidates"] = [intent["driver"]]
            intent["needs_clarification"] = False
            intent["clarification_message"] = None
        if overrides.get("event"):
            intent["event"] = overrides["event"]
        if overrides.get("year") is not None:
            intent["year"] = overrides["year"]
        if overrides.get("session_type"):
            intent["session_type"] = overrides["session_type"]
    return {**state, "intent": intent}


def resolve_followup_node(state: AgentState) -> AgentState:
    intent = copy.deepcopy(state["intent"])
    memory = state.get("memory") or {}
    query = state["query"]

    # If a driver was already found, we don't need to fallback
    if intent.get("driver"):
        intent["needs_clarification"] = False
        intent["clarification_message"] = None
        return {**state, "intent": intent}

    # Only skip if we have multiple drivers (actual ambiguity)
    if intent.get("needs_clarification") and intent.get("driver_candidates") and len(intent["driver_candidates"]) > 1:
        return {**state, "intent": intent}

    if not intent.get("driver") and COMPARE_PATTERN.search(query):
        intent["needs_clarification"] = True
        intent["clarification_message"] = (
            "Comparison query detected but target driver is missing. Please provide one driver code."
        )
        return {**state, "intent": intent}

    # Memory fallback logic for DRIVER
    if not intent.get("driver") and memory.get("last_driver"):
        q_lower = query.lower()
        is_explicit_followup = bool(FOLLOWUP_PATTERN.search(query))
        
        # Improved unknown driver detection: look for any word that is NOT a known driver, keyword, or common word
        words = re.findall(r"\b\w+\b", query)
        domain_tokens = set()
        for k in DOMAIN_KEYWORDS:
            for token in k.split():
                domain_tokens.add(token.upper())
                
        potential_unknown_drivers = [w for w in words 
                                   if w.upper() not in DRIVER_MAP 
                                   and w.upper() not in domain_tokens
                                   and w.lower() not in COMMON_WORDS
                                   and not w.isdigit()]
        
        # More restrictive short query check
        is_very_short_followup = len(query.split()) < 4 and any(k in q_lower for k in DOMAIN_KEYWORDS)
        
        if (is_explicit_followup or is_very_short_followup) and not potential_unknown_drivers:
            intent["driver"] = memory["last_driver"]
            intent["needs_clarification"] = False
            intent["clarification_message"] = None
        elif potential_unknown_drivers:
            intent["needs_clarification"] = True
            intent["clarification_message"] = f"I detected '{potential_unknown_drivers[0]}' but I only have data for official F1 drivers (e.g. HAM, VER, NOR). Please provide their 3-letter code."
        else:
            intent["needs_clarification"] = True
            intent["clarification_message"] = "Please provide a 3-letter driver code (for example: HAM, VER, NOR) or a full driver name."

    # Contextual fallbacks for Year, Session, Event
    if not YEAR_PATTERN.search(query) and memory.get("last_year"):
        intent["year"] = memory["last_year"]
    if not SESSION_PATTERN.search(query) and memory.get("last_session_type"):
        intent["session_type"] = memory["last_session_type"]
    if all(token not in query.upper() for token in ("JAPAN", "MONACO", "BRITISH", "SILVERSTONE")) and memory.get("last_event"):
        intent["event"] = memory["last_event"]

    # Final check for driver
    if not intent.get("driver"):
        intent["needs_clarification"] = True
        if not intent.get("clarification_message"):
            intent["clarification_message"] = "Please provide a 3-letter driver code (for example: HAM, VER, NOR) or a full driver name."

    return {**state, "intent": intent}


def run_analysis_node(state: AgentState) -> AgentState:
    intent = state["intent"]
    if intent["needs_clarification"]:
        return {**state, "error": intent["clarification_message"]}

    memory = state.get("memory") or {}
    new_memory_vals = {
        "last_query": state["query"],
        "last_event": intent["event"],
        "last_year": intent["year"],
        "last_session_type": intent["session_type"],
    }
    if intent.get("driver"):
        new_memory_vals["last_driver"] = intent["driver"]
    
    if intent.get("intent_type") == "strategy":
        strategy = strategy_analyzer(
            year=intent["year"],
            event=intent["event"],
            session_type=intent["session_type"],
            driver=intent["driver"],
        )
        new_memory_vals["last_strategy_data"] = strategy
        memory.update(new_memory_vals)
        return {
            **state,
            "strategy_data": strategy,
            "memory": memory,
            "retry_count": 0,
            "retry_metadata": {
                "max_retries": MAX_TOOL_RETRIES,
                "retry_backoff_seconds": RETRY_BACKOFF_SECONDS,
                "retryable_exhausted": False,
            },
        }

    telemetry, retry_count, retryable_exhausted = _call_with_retry(
        year=intent["year"],
        event=intent["event"],
        session_type=intent["session_type"],
        driver=intent["driver"],
    )
    if retryable_exhausted:
        return {
            **state,
            "telemetry_data": telemetry,
            "retry_count": retry_count,
            "retry_metadata": {
                "max_retries": MAX_TOOL_RETRIES,
                "retry_backoff_seconds": RETRY_BACKOFF_SECONDS,
                "retryable_exhausted": True,
            },
        }
    
    new_memory_vals["last_telemetry_data"] = telemetry
    memory.update(new_memory_vals)
    return {
        **state,
        "telemetry_data": telemetry,
        "memory": memory,
        "retry_count": retry_count,
        "retry_metadata": {
            "max_retries": MAX_TOOL_RETRIES,
            "retry_backoff_seconds": RETRY_BACKOFF_SECONDS,
            "retryable_exhausted": False,
        },
    }


def _render_template(state: AgentState) -> str:
    """Deterministic template rendering — the regression-safe fallback path."""
    if state.get("error"):
        return state["error"]

    if state.get("intent", {}).get("intent_type") == "strategy":
        strategy_bundle = state.get("strategy_data") or {}
        strategy = strategy_bundle.get("strategy") or {}
        if strategy_bundle.get("fallback"):
            message = strategy_bundle.get("fallback_reason") or "Strategy recommendation is unavailable for the current query."
            return f"Strategy unavailable: {message}"

        pit_window = strategy.get("recommended_pit_window_laps", [0, 0])
        confidence = strategy.get("confidence_band", "low")
        undercut_risk = strategy.get("undercut_risk", "unknown")
        return (
            f"Baseline strategy recommendation for {strategy_bundle['driver']}: consider pit window laps {pit_window[0]}-{pit_window[1]}. "
            f"Undercut risk is {undercut_risk} with {confidence} confidence."
        )

    telemetry = state.get("telemetry_data") or {}
    if telemetry.get("fallback"):
        message = telemetry.get("fallback_reason") or "Telemetry data is unavailable for the current query."
        return f"Telemetry unavailable: {message}"

    speed = telemetry["speed"]
    gear = telemetry["gear"]
    rpm = telemetry["rpm"]
    return (
        f"{telemetry['driver']} telemetry ({telemetry['event']} {telemetry['year']} {telemetry['session_type']}): "
        f"speed avg {speed['avg']:.1f} {speed['unit']} (min {speed['min']:.1f}, max {speed['max']:.1f}); "
        f"gear avg {gear['avg']:.1f}; rpm avg {rpm['avg']:.0f}."
    )


def _is_short_factual(state: AgentState) -> bool:
    """Error / fallback branches stay on the template — no value in routing them through Gemini."""
    if state.get("error"):
        return True
    if state.get("intent", {}).get("intent_type") == "strategy":
        strategy_bundle = state.get("strategy_data") or {}
        if strategy_bundle.get("fallback"):
            return True
    else:
        telemetry = state.get("telemetry_data") or {}
        if telemetry.get("fallback"):
            return True
    return False


def _build_llm_context(state: AgentState) -> dict[str, Any]:
    """Trim the agent state down to the facts the LLM is allowed to mention."""
    citations = state.get("citations") or []
    # Strip score before sending to the LLM — it's a retrieval-internal signal,
    # and including it tempts the model to mention numeric "confidence" values
    # the user never asked for.
    trimmed_citations = [
        {k: v for k, v in c.items() if k != "score"}
        for c in citations
    ]
    return {
        "intent": state.get("intent") or {},
        "telemetry_data": state.get("telemetry_data") or {},
        "strategy_data": state.get("strategy_data") or {},
        "citations": trimmed_citations,
    }


def format_response_node(state: AgentState) -> AgentState:
    if _is_short_factual(state):
        return {**state, "response_text": _render_template(state), "rationale_source": "template"}

    llm_text = generate_rationale(_build_llm_context(state))
    if llm_text:
        return {**state, "response_text": llm_text, "rationale_source": "llm"}

    return {**state, "response_text": _render_template(state), "rationale_source": "template"}


workflow = StateGraph(AgentState)
workflow.add_node("parse_intent", parse_intent_node)
workflow.add_node("resolve_followup", resolve_followup_node)
workflow.add_node("run_analysis", run_analysis_node)
workflow.add_node("format_response", format_response_node)
workflow.set_entry_point("parse_intent")
workflow.add_edge("parse_intent", "resolve_followup")
workflow.add_edge("resolve_followup", "run_analysis")
workflow.add_edge("run_analysis", "format_response")
workflow.add_edge("format_response", END)
app_graph = workflow.compile()


def _build_memory_snapshot() -> dict[str, Any]:
    if not MEMORY_STORE:
        return {"history": []}
    history = list(MEMORY_STORE)
    latest = history[-1]
    return {
        "history": history,
        "last_query": latest.get("last_query"),
        "last_driver": latest.get("last_driver"),
        "last_event": latest.get("last_event"),
        "last_year": latest.get("last_year"),
        "last_session_type": latest.get("last_session_type"),
        "last_telemetry_data": latest.get("last_telemetry_data"),
        "last_strategy_data": latest.get("last_strategy_data"),
    }


def reset_memory_store() -> None:
    MEMORY_STORE.clear()


def _is_retryable_fallback_reason(reason: str | None) -> bool:
    if not reason:
        return False
    normalized = reason.lower()
    return any(hint in normalized for hint in RETRYABLE_ERROR_HINTS)


def _call_with_retry(
    *,
    year: int,
    event: str,
    session_type: str,
    driver: str,
) -> tuple[dict[str, Any], int, bool]:
    retry_count = 0
    while True:
        telemetry = get_session_telemetry_summary(
            year=year,
            event=event,
            session_type=session_type,
            driver=driver,
        )
        fallback_reason = telemetry.get("fallback_reason")
        is_retryable = telemetry.get("fallback") and _is_retryable_fallback_reason(fallback_reason)
        if not is_retryable:
            return telemetry, retry_count, False
        if retry_count >= MAX_TOOL_RETRIES:
            return telemetry, retry_count, True
        retry_count += 1
        sleep(RETRY_BACKOFF_SECONDS)


def analyze_query(
    query: str,
    *,
    session_override: dict[str, Any] | None = None,
    driver_override: str | None = None,
) -> dict[str, Any]:
    import copy
    memory_snapshot = copy.deepcopy(_build_memory_snapshot())

    overrides: dict[str, Any] = {}
    if driver_override:
        overrides["driver"] = driver_override
    if session_override:
        for key in ("event", "year", "session_type"):
            if session_override.get(key) is not None:
                overrides[key] = session_override[key]

    termination_reason = "completed"
    start_time = monotonic()
    start_trace()
    citations: list[dict[str, Any]] = []
    if KNOWLEDGE_PATTERN.search(query or ""):
        try:
            citations = knowledge_lookup(query, 2) or []
        except Exception:  # noqa: BLE001 — retrieval must never break /analyze
            citations = []
    try:
        result = app_graph.invoke(
            {
                "query": query,
                "intent": {},
                "telemetry_data": {},
                "strategy_data": {},
                "response_text": "",
                "error": None,
                "memory": memory_snapshot,
                "retry_count": 0,
                "retry_metadata": {},
                "overrides": overrides,
                "rationale_source": "template",
                "citations": citations,
            },
            config={"recursion_limit": MAX_GRAPH_STEPS},
        )
    except Exception as exc:
        termination_reason = "graph_error"
        elapsed_ms = (monotonic() - start_time) * 1000
        return {
            "intent": {},
            "telemetry_data": {},
            "strategy_data": None,
            "response_text": "Could not process query due to graph execution error.",
            "error": str(exc),
            "rationale_source": "template",
            "memory": {
                "history_size": len(MEMORY_STORE),
                "retention_cap": MEMORY_RETENTION_CAP,
                "last_driver": memory_snapshot.get("last_driver"),
            },
            "execution": {
                "step_limit": MAX_GRAPH_STEPS,
                "duration_limit_seconds": MAX_GRAPH_DURATION_SECONDS,
                "duration_ms": elapsed_ms,
                "termination_reason": termination_reason,
                "trace": get_trace(),
            },
            "retry": {
                "count": 0,
                "max_retries": MAX_TOOL_RETRIES,
                "retryable_exhausted": False,
            },
            "citations": citations,
        }

    elapsed_ms = (monotonic() - start_time) * 1000
    if elapsed_ms > MAX_GRAPH_DURATION_SECONDS * 1000:
        termination_reason = "duration_limit_exceeded"

    if result.get("memory"):
        memory_entry = {
            "last_query": result["memory"].get("last_query"),
            "last_driver": result["memory"].get("last_driver"),
            "last_event": result["memory"].get("last_event"),
            "last_year": result["memory"].get("last_year"),
            "last_session_type": result["memory"].get("last_session_type"),
            "last_telemetry_data": result["memory"].get("last_telemetry_data"),
            "last_strategy_data": result["memory"].get("last_strategy_data"),
        }
        MEMORY_STORE.append(memory_entry)

    strategy_bundle = result.get("strategy_data") or {}
    strategy_payload = None
    if strategy_bundle:
        strategy_data = strategy_bundle.get("strategy") or {}
        pit_window = strategy_data.get("recommended_pit_window_laps", [])
        strategy_payload = {
            **strategy_data,
            "target_lap": pit_window[0] if pit_window else None,
            "fallback": strategy_bundle.get("fallback", False),
            "fallback_reason": strategy_bundle.get("fallback_reason"),
        }

    return {
        "intent": result["intent"],
        "telemetry_data": result.get("telemetry_data", {}),
        "strategy_data": strategy_payload,
        "response_text": result["response_text"],
        "rationale_source": result.get("rationale_source", "template"),
        "error": result.get("error"),
        "memory": {
            "history_size": len(MEMORY_STORE),
            "retention_cap": MEMORY_RETENTION_CAP,
            "last_driver": result.get("memory", {}).get("last_driver"),
        },
        "execution": {
            "step_limit": MAX_GRAPH_STEPS,
            "duration_limit_seconds": MAX_GRAPH_DURATION_SECONDS,
            "duration_ms": elapsed_ms,
            "termination_reason": termination_reason,
            "trace": get_trace(),
        },
        "retry": {
            "count": result.get("retry_count", 0),
            "max_retries": result.get("retry_metadata", {}).get("max_retries", MAX_TOOL_RETRIES),
            "retry_backoff_seconds": result.get("retry_metadata", {}).get("retry_backoff_seconds", RETRY_BACKOFF_SECONDS),
            "retryable_exhausted": result.get("retry_metadata", {}).get("retryable_exhausted", False),
        },
        "citations": citations,
    }
