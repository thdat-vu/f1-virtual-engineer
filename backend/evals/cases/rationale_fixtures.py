"""Fixtures for the LLM rationale eval harness.

Each fixture is a dict with:
- name: short slug for test parametrize ids.
- context: dict shaped like _build_llm_context output (intent + telemetry_data
  + strategy_data + citations).
- expected_substrings: every string MUST appear in the model output (case-
  insensitive). Pin the load-bearing facts the engineer voice should never
  drop — driver code, event, key numbers, or quoted citation titles.
- forbidden_substrings: strings the model MUST NOT produce. Used to catch
  hallucinated drivers, invented lap numbers, or boilerplate preambles
  ("Here is the summary…") that the system prompt forbids.

Add a new fixture by appending to FIXTURES — no harness change needed.
Keep contexts compact: one or two telemetry channels, not full payloads.
"""

from typing import Any

FIXTURES: list[dict[str, Any]] = [
    {
        "name": "telemetry_ham_japan_2023",
        "context": {
            "intent": {
                "driver": "HAM",
                "year": 2023,
                "event": "Japanese Grand Prix",
                "session_type": "R",
                "intent_type": "telemetry",
            },
            "telemetry_data": {
                "driver": "HAM",
                "year": 2023,
                "event": "Japanese Grand Prix",
                "session_type": "R",
                "speed": {"avg": 218.0, "max": 312.0, "unit": "km/h"},
                "fallback": False,
            },
            "strategy_data": {},
            "citations": [],
        },
        "expected_substrings": ["HAM"],
        "forbidden_substrings": ["here is", "VER", "MAX", "##"],
    },
    {
        "name": "strategy_ver_pit_window",
        "context": {
            "intent": {
                "driver": "VER",
                "year": 2024,
                "event": "Italian Grand Prix",
                "session_type": "R",
                "intent_type": "strategy",
            },
            "telemetry_data": {},
            "strategy_data": {
                "recommended_pit_window_laps": [22, 26],
                "target_lap": 22,
                "undercut_risk": "high",
                "overcut_risk": "low",
                "confidence_band": "medium",
                "fallback": False,
            },
            "citations": [],
        },
        "expected_substrings": ["VER", "22"],
        "forbidden_substrings": ["here is", "HAM", "Article", "##"],
    },
    {
        "name": "strategy_with_drs_citation",
        "context": {
            "intent": {
                "driver": "NOR",
                "year": 2024,
                "event": "Monza",
                "session_type": "R",
                "intent_type": "strategy",
            },
            "telemetry_data": {},
            "strategy_data": {
                "recommended_pit_window_laps": [18, 22],
                "target_lap": 18,
                "undercut_risk": "medium",
                "confidence_band": "medium",
                "fallback": False,
            },
            "citations": [
                {
                    "id": "drs-activation",
                    "title": "Drag Reduction System (DRS) activation rules",
                    "section": "22.1 — Drag Reduction System",
                    "topics": ["drs", "overtaking"],
                    "snippet": "DRS may only be activated when within one second of the car ahead at the designated detection point.",
                    "source": "FIA Sporting Regs 2024, Article 22.1",
                },
            ],
        },
        "expected_substrings": ["NOR", "DRS"],
        "forbidden_substrings": ["here is", "Article 23", "Article 21", "##"],
    },
    {
        "name": "strategy_with_safety_car_citation",
        "context": {
            "intent": {
                "driver": "LEC",
                "year": 2024,
                "event": "Monaco",
                "session_type": "R",
                "intent_type": "strategy",
            },
            "telemetry_data": {},
            "strategy_data": {
                "recommended_pit_window_laps": [11, 15],
                "target_lap": 11,
                "undercut_risk": "low",
                "confidence_band": "high",
                "fallback": False,
            },
            "citations": [
                {
                    "id": "safety-car",
                    "title": "Safety Car deployment and restart procedure",
                    "section": "55 — Safety Car",
                    "topics": ["safety-car", "restart"],
                    "snippet": "When the Safety Car is deployed, all competitors must reduce speed and may not overtake.",
                    "source": "FIA Sporting Regs 2024, Article 55",
                },
            ],
        },
        "expected_substrings": ["LEC", "Safety Car"],
        "forbidden_substrings": ["here is", "VER", "##"],
    },
    {
        "name": "telemetry_fallback_thin_context",
        "context": {
            "intent": {
                "driver": "PIA",
                "year": 2024,
                "event": "British Grand Prix",
                "session_type": "Q",
                "intent_type": "telemetry",
            },
            "telemetry_data": {
                "driver": "PIA",
                "year": 2024,
                "event": "British Grand Prix",
                "session_type": "Q",
                "fallback": True,
                "fallback_reason": "FastF1 returned no laps for the requested driver.",
            },
            "strategy_data": {},
            "citations": [],
        },
        "expected_substrings": ["PIA"],
        # The model should not fabricate speed/gear values when telemetry is
        # missing — guard against the most obvious hallucinations.
        "forbidden_substrings": ["km/h", "rpm", "here is", "##"],
    },
    {
        "name": "telemetry_min_max_avg_present",
        "context": {
            "intent": {
                "driver": "RUS",
                "year": 2024,
                "event": "Spanish Grand Prix",
                "session_type": "R",
                "intent_type": "telemetry",
            },
            "telemetry_data": {
                "driver": "RUS",
                "year": 2024,
                "event": "Spanish Grand Prix",
                "session_type": "R",
                "speed": {"min": 88.0, "max": 318.0, "avg": 207.0, "unit": "km/h"},
                "fallback": False,
            },
            "strategy_data": {},
            "citations": [],
        },
        "expected_substrings": ["RUS"],
        "forbidden_substrings": ["VER", "HAM", "here is", "##"],
    },
]
