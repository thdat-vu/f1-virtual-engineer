import os
from typing import Any

import fastf1
import pandas as pd

# Setup caching for FastF1
# Ensure the backend/data directory exists
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

fastf1.Cache.enable_cache(CACHE_DIR)


SERIES_POINTS = 200


def _downsample(values: pd.Series, points: int = SERIES_POINTS) -> list[float]:
    """Reduce a numeric Series to a fixed-length list using mean-bucket aggregation."""
    n = len(values)
    if n == 0:
        return []
    if n <= points:
        return [float(v) for v in values.tolist()]
    # Bucket the series into `points` equally sized chunks; take the mean of each.
    bucket_indices = (pd.Series(range(n)) * points // n).to_numpy()
    grouped = values.reset_index(drop=True).groupby(bucket_indices).mean()
    return [float(v) for v in grouped.tolist()]


def _stats(series: pd.Series, unit: str) -> dict[str, Any]:
    values = series.dropna()
    return {
        "min": float(values.min()),
        "max": float(values.max()),
        "avg": float(values.mean()),
        "unit": unit,
        "series": _downsample(values),
    }


def _normalize_telemetry(
    telemetry: pd.DataFrame,
    *,
    year: int,
    event: str,
    session_type: str,
    driver: str,
) -> dict[str, Any]:
    required_columns = {"Speed": "km/h", "nGear": "gear", "RPM": "rpm"}
    missing = [col for col in required_columns if col not in telemetry.columns]
    if missing:
        raise ValueError(f"Missing required telemetry channels: {', '.join(missing)}")

    result: dict[str, Any] = {
        "driver": driver,
        "year": year,
        "event": event,
        "session_type": session_type,
        "sample_points": int(len(telemetry.index)),
        "speed": _stats(telemetry["Speed"], "km/h"),
        "gear": _stats(telemetry["nGear"], "gear"),
        "rpm": _stats(telemetry["RPM"], "rpm"),
        "source": "fastf1",
        "fallback": False,
        "fallback_reason": None,
    }

    # Throttle and brake are optional — not all sessions include them
    if "Throttle" in telemetry.columns:
        result["throttle"] = _stats(telemetry["Throttle"], "%")
    if "Brake" in telemetry.columns:
        # Brake is boolean in FastF1; convert to 0/1 then express as %
        brake_series = telemetry["Brake"].astype(float) * 100
        result["brake"] = _stats(brake_series, "%")

    return result


def get_year_schedule(year: int) -> list[dict[str, Any]]:
    """
    Fetch the event schedule for a specific year and return a list of event dictionaries.
    """
    try:
        schedule = fastf1.get_event_schedule(year)
        # Filter for official race events (Grand Prix) and testing if needed
        # We'll return EventName and Location for the UI
        events = []
        for _, row in schedule.iterrows():
            events.append({
                "name": row["EventName"],
                "location": row["Location"],
                "round": int(row["RoundNumber"]),
                "official_name": row["OfficialEventName"]
            })
        return events
    except Exception as exc:
        print(f"Error fetching schedule for {year}: {exc}")
        return []


def get_event_drivers(year: int, event: str) -> dict[str, Any]:
    """
    Return the driver roster (3-letter codes) for an event in `year`.

    Tries the Race session first, then Qualifying as a fallback (useful for
    upcoming events where no race has run yet). Returns a structured envelope
    so the API endpoint can surface fallback reasons to the UI rather than 500.
    """
    last_error: str = "No drivers found in Race or Qualifying laps."
    for session_type in ("R", "Q"):
        try:
            session = fastf1.get_session(year, event, session_type)
            session.load(laps=True, telemetry=False, weather=False, messages=False)
            laps = session.laps
            if laps.empty:
                continue
            drivers = sorted({str(d).upper() for d in laps["Driver"].dropna().unique() if str(d)})
            if drivers:
                return {
                    "year": year,
                    "event": event,
                    "drivers": drivers,
                    "source_session": session_type,
                    "fallback": False,
                    "fallback_reason": None,
                }
        except Exception as exc:  # noqa: BLE001 — surface any FastF1 failure to caller
            last_error = str(exc)

    return {
        "year": year,
        "event": event,
        "drivers": [],
        "source_session": None,
        "fallback": True,
        "fallback_reason": last_error,
    }


def get_session_telemetry_summary(
    year: int,
    event: str,
    session_type: str,
    driver: str,
) -> dict[str, Any]:
    """
    Fetch telemetry summary (speed, gear, rpm) for a specific driver/session.
    Returns a normalized dictionary that matches API schema.
    """
    driver = driver.upper()

    try:
        session = fastf1.get_session(year, event, session_type)
        # Optimization: only load laps and telemetry for this summary
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        laps = session.laps.pick_driver(driver)
        if laps.empty:
            return {
                "driver": driver,
                "year": year,
                "event": event,
                "session_type": session_type,
                "sample_points": 0,
                "speed": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "km/h", "series": []},
                "gear": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "gear", "series": []},
                "rpm": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "rpm", "series": []},
                "source": "fastf1",
                "fallback": True,
                "fallback_reason": "No laps found for requested driver/session.",
            }

        fastest_lap = laps.pick_fastest()
        telemetry = fastest_lap.get_telemetry()
        return _normalize_telemetry(
            telemetry,
            year=year,
            event=event,
            session_type=session_type,
            driver=driver,
        )
    except Exception as exc:
        return {
            "driver": driver,
            "year": year,
            "event": event,
            "session_type": session_type,
            "sample_points": 0,
            "speed": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "km/h", "series": []},
            "gear": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "gear", "series": []},
            "rpm": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "rpm", "series": []},
            "source": "fastf1",
            "fallback": True,
            "fallback_reason": str(exc),
        }


def extract_tyre_wear_features(
    year: int,
    event: str,
    session_type: str,
    driver: str,
) -> dict[str, Any]:
    """
    Derive tyre-wear features used for downstream prediction.
    Features include lap-time decay, stint progression, and temperature trend flags.
    """
    driver = driver.upper()
    try:
        session = fastf1.get_session(year, event, session_type)
        # Optimization: only load laps and weather for strategy analysis
        session.load(laps=True, telemetry=False, weather=True, messages=False)
        laps = session.laps.pick_driver(driver)
        if laps.empty:
            return {
                "driver": driver,
                "year": year,
                "event": event,
                "session_type": session_type,
                "fallback": True,
                "fallback_reason": "No laps found for requested driver/session.",
                "features": {
                    "lap_count": 0,
                    "stint_count": 0,
                    "lap_time_decay_seconds_per_lap": 0.0,
                    "stint_progress_ratio": 0.0,
                    "avg_track_temp_c": None,
                    "track_temp_trend_c_per_lap": None,
                    "temperature_missing": True,
                },
            }

        lap_seconds = laps["LapTime"].dt.total_seconds().dropna().reset_index(drop=True)
        if len(lap_seconds) <= 1:
            lap_time_decay = 0.0
        else:
            lap_time_decay = float((lap_seconds.iloc[-1] - lap_seconds.iloc[0]) / (len(lap_seconds) - 1))

        stint_series = laps["Stint"].dropna()
        stint_count = int(stint_series.nunique()) if not stint_series.empty else 0
        if stint_count > 0 and not stint_series.empty:
            current_stint = int(stint_series.iloc[-1])
            laps_in_current = laps[laps["Stint"] == current_stint]
            stint_progress_ratio = float(len(laps_in_current) / len(laps))
        else:
            stint_progress_ratio = 0.0

        weather = session.weather_data if hasattr(session, "weather_data") else None
        avg_track_temp = None
        temp_trend = None
        temperature_missing = True
        if weather is not None and not weather.empty and "TrackTemp" in weather.columns:
            track_temp = weather["TrackTemp"].dropna().reset_index(drop=True)
            if not track_temp.empty:
                avg_track_temp = float(track_temp.mean())
                if len(track_temp) > 1:
                    temp_trend = float((track_temp.iloc[-1] - track_temp.iloc[0]) / (len(track_temp) - 1))
                else:
                    temp_trend = 0.0
                temperature_missing = False

        return {
            "driver": driver,
            "year": year,
            "event": event,
            "session_type": session_type,
            "fallback": False,
            "fallback_reason": None,
            "features": {
                "lap_count": int(len(laps)),
                "stint_count": stint_count,
                "lap_time_decay_seconds_per_lap": lap_time_decay,
                "stint_progress_ratio": stint_progress_ratio,
                "avg_track_temp_c": avg_track_temp,
                "track_temp_trend_c_per_lap": temp_trend,
                "temperature_missing": temperature_missing,
            },
        }
    except Exception as exc:
        return {
            "driver": driver,
            "year": year,
            "event": event,
            "session_type": session_type,
            "fallback": True,
            "fallback_reason": str(exc),
            "features": {
                "lap_count": 0,
                "stint_count": 0,
                "lap_time_decay_seconds_per_lap": 0.0,
                "stint_progress_ratio": 0.0,
                "avg_track_temp_c": None,
                "track_temp_trend_c_per_lap": None,
                "temperature_missing": True,
            },
        }

if __name__ == "__main__":
    # Test script: Fetch Hamilton's telemetry from 2023 Japan GP
    print("Fetching Lewis Hamilton's telemetry from 2023 Japanese GP...")
    summary = get_session_telemetry_summary(2023, "Japanese Grand Prix", "R", "HAM")
    print(summary)
