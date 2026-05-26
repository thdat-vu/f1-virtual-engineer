"""Weather summary for a session (#235).

A pit-call helper that's been ignored by every endpoint so far.
Real F1 strategy hinges on track temp (tyre warm-up window),
rainfall (compound switch decision), and to a lesser extent air
temp + humidity. We surface a compact summary so the frontend can
render a header pill and the cross-year chart can flag mismatched
conditions between two seasons.

Same fail-closed envelope contract as the other FastF1 helpers:
any error → `fallback: True` + a populated reason, never raise.
The session weather_data DataFrame has these columns when present:
``Time, AirTemp, Humidity, Pressure, Rainfall, TrackTemp,
WindDirection, WindSpeed``. Some practice sessions don't carry
weather (the broadcast feed wasn't recording); we degrade silently.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import fastf1

_logger = logging.getLogger(__name__)

Condition = Literal["DRY", "MIXED", "WET"]

# Fraction of weather samples reporting rain that flips the
# label. 30% chosen so a single shower in an otherwise-dry session
# reads as MIXED rather than WET — strategy implications differ
# meaningfully (compound switch vs no switch).
_WET_THRESHOLD = 0.30
_DRY_THRESHOLD = 0.0


def _empty_envelope(*, reason: str) -> dict[str, Any]:
    return {
        "condition": None,
        "air_temp_c": None,
        "track_temp_c": None,
        "rainfall_fraction": None,
        "humidity_pct": None,
        "wind_speed_kmh": None,
        "fallback": True,
        "fallback_reason": reason,
    }


def _classify(rainfall_fraction: float) -> Condition:
    if rainfall_fraction <= _DRY_THRESHOLD:
        return "DRY"
    if rainfall_fraction < _WET_THRESHOLD:
        return "MIXED"
    return "WET"


def get_weather_summary(year: int, event: str, session_type: str) -> dict[str, Any]:
    """Per-session weather aggregate. Always returns a populated envelope."""
    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=False, telemetry=False, weather=True, messages=False)
    except Exception as exc:  # noqa: BLE001
        return _empty_envelope(reason=f"Session load failed: {exc}")

    weather = getattr(session, "weather_data", None)
    if weather is None or len(weather) == 0:
        return _empty_envelope(reason="No weather samples in session.")

    try:
        rainfall_fraction = float(weather["Rainfall"].mean()) if "Rainfall" in weather.columns else 0.0
        air_temp = float(weather["AirTemp"].mean()) if "AirTemp" in weather.columns else None
        track_temp = float(weather["TrackTemp"].mean()) if "TrackTemp" in weather.columns else None
        humidity = float(weather["Humidity"].mean()) if "Humidity" in weather.columns else None
        wind = float(weather["WindSpeed"].mean()) if "WindSpeed" in weather.columns else None
    except Exception as exc:  # noqa: BLE001 — degrade rather than 5xx on schema drift
        return _empty_envelope(reason=f"Weather aggregation failed: {exc}")

    return {
        "condition": _classify(rainfall_fraction),
        "air_temp_c": round(air_temp, 1) if air_temp is not None else None,
        "track_temp_c": round(track_temp, 1) if track_temp is not None else None,
        "rainfall_fraction": round(rainfall_fraction, 3),
        "humidity_pct": round(humidity, 1) if humidity is not None else None,
        "wind_speed_kmh": round(wind, 1) if wind is not None else None,
        "fallback": False,
        "fallback_reason": None,
    }
