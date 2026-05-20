from typing import Any

from core.trace import traced
from tools.fastf1_helper import (
    extract_tyre_wear_features as _raw_extract_tyre_wear_features,
    get_current_gap_to_ahead,
    get_gap_to_competitor,
)

extract_tyre_wear_features = traced("tyre_wear")(_raw_extract_tyre_wear_features)

# Default fallback gap when FastF1 can't tell us where the car ahead is.
# 1.2s used to be the hardcoded value; keeping it as the fallback so a
# FastF1 hiccup degrades to "assume tight battle" rather than blanking
# the undercut/overcut classification entirely.
_GAP_FALLBACK_SECONDS = 1.2


def predict_tyre_wear(
    year: int,
    event: str,
    session_type: str,
    driver: str,
) -> dict[str, Any]:
    """
    Baseline heuristic tyre wear predictor using extracted telemetry features.
    """
    extracted = extract_tyre_wear_features(year, event, session_type, driver)
    features = extracted["features"]

    if extracted["fallback"]:
        return {
            "driver": driver.upper(),
            "year": year,
            "event": event,
            "session_type": session_type,
            "fallback": True,
            "fallback_reason": extracted["fallback_reason"],
            "prediction": {
                "degradation_rate_seconds_per_lap": 0.0,
                "confidence_band": "low",
                "expected_performance_drop_window_laps": [0, 0],
                "reasons": ["No tyre-wear features available."],
            },
        }

    lap_decay = float(features["lap_time_decay_seconds_per_lap"])
    stint_progress = float(features["stint_progress_ratio"])
    temp_trend = features["track_temp_trend_c_per_lap"]
    temp_trend_value = float(temp_trend) if temp_trend is not None else 0.0

    degradation_rate = lap_decay + (0.05 * stint_progress) + (0.02 * temp_trend_value)
    degradation_rate = max(degradation_rate, 0.0)

    if features["temperature_missing"]:
        confidence = "medium" if degradation_rate < 0.25 else "low"
        reasons = [
            "Track temperature data is missing; model confidence reduced.",
            "Prediction uses lap-time decay and stint progression only.",
        ]
    else:
        confidence = "high" if degradation_rate < 0.25 else ("medium" if degradation_rate < 0.45 else "low")
        reasons = [
            "Prediction combines lap-time decay, stint progression, and track temperature trend.",
        ]

    if degradation_rate < 0.2:
        drop_window = [12, 18]
    elif degradation_rate < 0.4:
        drop_window = [8, 14]
    else:
        drop_window = [4, 10]

    return {
        "driver": driver.upper(),
        "year": year,
        "event": event,
        "session_type": session_type,
        "fallback": False,
        "fallback_reason": None,
        "prediction": {
            "degradation_rate_seconds_per_lap": round(degradation_rate, 4),
            "confidence_band": confidence,
            "expected_performance_drop_window_laps": drop_window,
            "reasons": reasons,
        },
        "features_used": features,
    }


def strategy_analyzer(
    year: int,
    event: str,
    session_type: str,
    driver: str,
    current_gap_seconds: float | None = None,
    target_driver: str | None = None,
) -> dict[str, Any]:
    """
    Build pit-window recommendation using tyre wear prediction and pace assumptions.

    Gap resolution order:
    1. ``current_gap_seconds`` — explicit override, skips FastF1 entirely.
    2. ``target_driver`` — measure gap to a specific competitor (slice 1B
       of #168). The competitor may be ahead or behind; the panel still
       classifies undercut/overcut from ``driver``'s perspective.
    3. Otherwise — gap to the car directly ahead (slice 1A default).

    Falls back to the legacy 1.2s assumption when the chosen lookup
    returns a fallback envelope.
    """
    tyre_prediction = predict_tyre_wear(year, event, session_type, driver)

    if tyre_prediction["fallback"]:
        return {
            "driver": driver.upper(),
            "year": year,
            "event": event,
            "session_type": session_type,
            "fallback": True,
            "fallback_reason": tyre_prediction["fallback_reason"],
            "strategy": {
                "recommended_pit_window_laps": [0, 0],
                "undercut_risk": "unknown",
                "overcut_risk": "unknown",
                "confidence_band": "low",
                "assumptions": ["Tyre features unavailable; cannot compute reliable strategy."],
                "rationale": ["Strategy analyzer requires valid tyre-wear prediction inputs."],
            },
        }

    competitor: str | None = None
    competitor_position_relative: str | None = None
    gap_lap: int | None = None
    gap_source: str
    if current_gap_seconds is not None:
        resolved_gap = float(current_gap_seconds)
        gap_source = "explicit"
    elif target_driver:
        gap_envelope = get_gap_to_competitor(
            year, event, session_type, driver, target_driver
        )
        if gap_envelope.get("fallback") or gap_envelope.get("gap_seconds") is None:
            resolved_gap = _GAP_FALLBACK_SECONDS
            gap_source = "fallback"
            competitor = target_driver.upper()
        else:
            resolved_gap = float(gap_envelope["gap_seconds"])
            competitor = target_driver.upper()
            competitor_position_relative = gap_envelope.get("competitor_position_relative")
            gap_lap = gap_envelope.get("lap_number")
            gap_source = "fastf1"
    else:
        gap_envelope = get_current_gap_to_ahead(year, event, session_type, driver)
        if gap_envelope.get("fallback") or gap_envelope.get("gap_seconds") is None:
            resolved_gap = _GAP_FALLBACK_SECONDS
            gap_source = "fallback"
        else:
            resolved_gap = float(gap_envelope["gap_seconds"])
            competitor = gap_envelope.get("driver_ahead")
            competitor_position_relative = "ahead"
            gap_lap = gap_envelope.get("lap_number")
            gap_source = "fastf1"

    prediction = tyre_prediction["prediction"]
    degradation_rate = float(prediction["degradation_rate_seconds_per_lap"])
    drop_window = prediction["expected_performance_drop_window_laps"]

    start_lap = max(drop_window[0], 4)
    end_lap = max(drop_window[1], start_lap + 2)
    pit_window = [start_lap, end_lap]

    undercut_risk = "high" if resolved_gap <= 1.5 and degradation_rate >= 0.25 else (
        "medium" if resolved_gap <= 2.5 else "low"
    )
    overcut_risk = "high" if degradation_rate >= 0.45 else ("medium" if degradation_rate >= 0.25 else "low")

    if competitor:
        rel = (
            f" ({competitor_position_relative})"
            if competitor_position_relative in ("ahead", "behind")
            else ""
        )
        gap_assumption = f"Current gap to {competitor}{rel}: {resolved_gap:.1f}s."
    else:
        gap_assumption = f"Current gap to rival considered: {resolved_gap:.1f}s."
    assumptions = [
        gap_assumption,
        "Historical pace delta assumed stable over next 5 laps.",
        "Tyre performance follows extracted degradation trend.",
    ]
    rationale = [
        f"Predicted degradation rate: {degradation_rate:.3f}s/lap.",
        f"Expected performance drop window from predictor: laps {drop_window[0]}-{drop_window[1]}.",
        f"Undercut risk classified as {undercut_risk} based on gap and wear trend.",
    ]

    return {
        "driver": driver.upper(),
        "year": year,
        "event": event,
        "session_type": session_type,
        "fallback": False,
        "fallback_reason": None,
        "strategy": {
            "recommended_pit_window_laps": pit_window,
            "undercut_risk": undercut_risk,
            "overcut_risk": overcut_risk,
            "confidence_band": prediction["confidence_band"],
            "assumptions": assumptions,
            "rationale": rationale,
            "current_gap_seconds": round(resolved_gap, 2),
            "gap_source": gap_source,
            "competitor_ahead": competitor,
            "competitor_position_relative": competitor_position_relative,
            "gap_sampled_at_lap": gap_lap,
        },
        "tyre_prediction": prediction,
    }
