import gzip
import hashlib
import json
import logging
import os
import threading
from functools import wraps
from typing import Any, Callable

import fastf1
import pandas as pd
from cachetools import TTLCache

_logger = logging.getLogger(__name__)

# Setup caching for FastF1
# Ensure the backend/data directory exists
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

fastf1.Cache.enable_cache(CACHE_DIR)


SERIES_POINTS = 200


# In-process result caches for FastF1 helpers (#100 slice B).
#
# Why a custom wrapper instead of `@cachetools.cached`:
# the helpers return *fallback dicts* on failure (network blip, FastF1
# decode error) rather than raising. We must not cache those — otherwise
# a transient error sticks for hours. The wrapper below caches only when
# the result is "good" (per `is_good`), and treats anything else as a
# pass-through to the underlying call.
#
# TTLs:
# - Schedule / roster / lap list: 24h. Past events are immutable; for the
#   current weekend a 24h drift is acceptable on an MVP demo (cache is
#   per-process anyway, restart clears it).
# - Telemetry summary / tyre features: 1h. Same immutability argument
#   but the entries are bulkier, so we keep the window tighter to bound
#   memory.
#
# Caches are *per-process* (single uvicorn worker for the MVP). For multi-
# worker / multi-pod deployment, slice D of #100 moves this to Redis.

_schedule_cache: TTLCache = TTLCache(maxsize=32, ttl=86400)
_roster_cache: TTLCache = TTLCache(maxsize=128, ttl=86400)
_lap_list_cache: TTLCache = TTLCache(maxsize=256, ttl=86400)
_telemetry_cache: TTLCache = TTLCache(maxsize=256, ttl=3600)
_tyre_features_cache: TTLCache = TTLCache(maxsize=256, ttl=3600)
_cache_lock = threading.Lock()


# Pre-bake (slice C of #100):
# Helper outputs can be persisted to disk so the first user after a restart
# gets a warm cache hit instead of paying the multi-second FastF1 cold load.
#
# - PREBAKE_DIR layout: one subdir per helper name, one gzipped JSON file per
#   call, named by a short SHA-256 of the args. The file body stores the
#   original args+kwargs alongside the result so loading can re-derive the
#   cache key without trusting the filename.
# - Recording is opt-in via FASTF1_PREBAKE_WRITE=true. Normal serving never
#   writes to disk — only `scripts/prebake.py` flips the flag.
# - Loading is always-on: `load_prebaked_into_caches()` runs at startup and
#   any entries that match the wrapper's key shape get seeded into the
#   in-memory TTLCache with full TTL.
#
# Format note: gzipped JSON, not parquet. The helper outputs are dict
# envelopes (numbers + short strings + a few 200-element float arrays).
# Parquet's row-oriented schema is a bad fit for these dict shapes and would
# pull pyarrow onto the import path. gzip+json keeps each entry under ~5 KB.

PREBAKE_DIR = os.path.join(CACHE_DIR, "prebake")
_PREBAKE_NAMES: dict[str, TTLCache] = {}  # name -> cache, populated by _ttl_cached


def _prebake_recording_enabled() -> bool:
    return os.environ.get("FASTF1_PREBAKE_WRITE", "").lower() == "true"


def _stable_key_digest(args: tuple, kwargs: dict) -> str:
    payload = json.dumps(
        {"args": list(args), "kwargs": kwargs}, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _write_prebake_entry(name: str, args: tuple, kwargs: dict, result: Any) -> None:
    subdir = os.path.join(PREBAKE_DIR, name)
    try:
        os.makedirs(subdir, exist_ok=True)
        digest = _stable_key_digest(args, kwargs)
        path = os.path.join(subdir, f"{digest}.json.gz")
        body = {"args": list(args), "kwargs": kwargs, "result": result}
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(body, fh, default=str)
    except Exception:  # noqa: BLE001 — persistence must never break a call
        _logger.warning("Prebake write failed for %s", name, exc_info=True)


def load_prebaked_into_caches() -> int:
    """Seed every TTLCache from the prebake dir. Returns count loaded.

    Called once at app startup. Silently ignores files it can't decode so a
    single corrupt entry doesn't break warmup. Safe to re-run."""
    if not os.path.isdir(PREBAKE_DIR):
        return 0
    loaded = 0
    for name, cache in _PREBAKE_NAMES.items():
        subdir = os.path.join(PREBAKE_DIR, name)
        if not os.path.isdir(subdir):
            continue
        for fname in os.listdir(subdir):
            if not fname.endswith(".json.gz"):
                continue
            path = os.path.join(subdir, fname)
            try:
                with gzip.open(path, "rt", encoding="utf-8") as fh:
                    entry = json.load(fh)
                args = tuple(entry["args"])
                kwargs = entry["kwargs"]
                result = entry["result"]
                key = (args, tuple(sorted(kwargs.items())))
                with _cache_lock:
                    cache[key] = result
                loaded += 1
            except Exception:  # noqa: BLE001
                _logger.warning("Skipping unreadable prebake entry %s", path, exc_info=True)
                continue
    return loaded


def _ttl_cached(
    cache: TTLCache,
    is_good: Callable[[Any], bool],
    name: str,
) -> Callable:
    """Cache only "good" results. Fallback/empty results bypass the cache
    so transient errors don't get pinned for the full TTL.

    `name` identifies the cache in the prebake dir layout (slice C of #100)."""

    _PREBAKE_NAMES[name] = cache

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            with _cache_lock:
                if key in cache:
                    return cache[key]
            result = func(*args, **kwargs)
            if is_good(result):
                with _cache_lock:
                    cache[key] = result
                if _prebake_recording_enabled():
                    _write_prebake_entry(name, args, kwargs, result)
            return result

        wrapper.cache_clear = lambda: _clear_cache(cache)  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _clear_cache(cache: TTLCache) -> None:
    with _cache_lock:
        cache.clear()


def _reset_caches_for_tests() -> None:
    """Wipe every helper cache. Tests call this in setUp to isolate state."""
    for cache in (
        _schedule_cache,
        _roster_cache,
        _lap_list_cache,
        _telemetry_cache,
        _tyre_features_cache,
    ):
        _clear_cache(cache)


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


def _lap_time_features(chosen_lap: pd.Series | None) -> tuple[float | None, list[float]]:
    """Extract (lap_duration_s, sector_boundaries_s) from a Lap row.

    `sector_boundaries_s` is `[s1_end, s2_end]` measured in seconds-from-lap-start.
    Both values are dropped if any sector time is missing — partial boundaries
    would mislead the chart's x-axis.
    """
    if chosen_lap is None:
        return None, []
    lap_time = chosen_lap.get("LapTime") if hasattr(chosen_lap, "get") else None
    duration: float | None = None
    if lap_time is not None and not pd.isna(lap_time):
        try:
            duration = float(lap_time.total_seconds())
        except AttributeError:
            duration = None

    s1 = chosen_lap.get("Sector1Time") if hasattr(chosen_lap, "get") else None
    s2 = chosen_lap.get("Sector2Time") if hasattr(chosen_lap, "get") else None
    boundaries: list[float] = []
    if s1 is not None and s2 is not None and not pd.isna(s1) and not pd.isna(s2):
        try:
            s1_end = float(s1.total_seconds())
            s2_end = s1_end + float(s2.total_seconds())
            boundaries = [s1_end, s2_end]
        except AttributeError:
            boundaries = []
    return duration, boundaries


def _normalize_telemetry(
    telemetry: pd.DataFrame,
    *,
    year: int,
    event: str,
    session_type: str,
    driver: str,
    chosen_lap: pd.Series | None = None,
) -> dict[str, Any]:
    required_columns = {"Speed": "km/h", "nGear": "gear", "RPM": "rpm"}
    missing = [col for col in required_columns if col not in telemetry.columns]
    if missing:
        raise ValueError(f"Missing required telemetry channels: {', '.join(missing)}")

    lap_duration_s, sector_boundaries_s = _lap_time_features(chosen_lap)

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
        "lap_duration_s": lap_duration_s,
        "sector_boundaries_s": sector_boundaries_s,
    }

    # Throttle and brake are optional — not all sessions include them
    if "Throttle" in telemetry.columns:
        result["throttle"] = _stats(telemetry["Throttle"], "%")
    if "Brake" in telemetry.columns:
        # Brake is boolean in FastF1; convert to 0/1 then express as %
        brake_series = telemetry["Brake"].astype(float) * 100
        result["brake"] = _stats(brake_series, "%")

    return result


@_ttl_cached(_schedule_cache, is_good=lambda r: bool(r), name="schedule")
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


@_ttl_cached(_roster_cache, is_good=lambda r: not r.get("fallback"), name="roster")
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


@_ttl_cached(_telemetry_cache, is_good=lambda r: not r.get("fallback"), name="telemetry")
def get_session_telemetry_summary(
    year: int,
    event: str,
    session_type: str,
    driver: str,
    lap_number: int | None = None,
) -> dict[str, Any]:
    """
    Fetch telemetry summary (speed, gear, rpm) for a specific driver/session.
    When `lap_number` is provided, telemetry is taken from that specific lap;
    otherwise the driver's fastest lap is used.
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
                "lap_duration_s": None,
                "sector_boundaries_s": [],
                "source": "fastf1",
                "fallback": True,
                "fallback_reason": "No laps found for requested driver/session.",
                "lap_number": None,
            }

        if lap_number is not None:
            matches = laps[laps["LapNumber"] == lap_number]
            if matches.empty:
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
                    "fallback_reason": f"Lap {lap_number} not found for driver {driver}.",
                    "lap_number": lap_number,
                }
            chosen_lap = matches.iloc[0]
            chosen_lap_number = int(lap_number)
        else:
            chosen_lap = laps.pick_fastest()
            chosen_lap_number = (
                int(chosen_lap["LapNumber"]) if "LapNumber" in chosen_lap and pd.notna(chosen_lap["LapNumber"]) else None
            )

        telemetry = chosen_lap.get_telemetry()
        result = _normalize_telemetry(
            telemetry,
            year=year,
            event=event,
            session_type=session_type,
            driver=driver,
            chosen_lap=chosen_lap,
        )
        result["lap_number"] = chosen_lap_number
        return result
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
            "lap_duration_s": None,
            "sector_boundaries_s": [],
            "source": "fastf1",
            "fallback": True,
            "fallback_reason": str(exc),
            "lap_number": lap_number,
        }


@_ttl_cached(_lap_list_cache, is_good=lambda r: not r.get("fallback"), name="lap_list")
def get_session_lap_list(
    year: int,
    event: str,
    session_type: str,
    driver: str,
) -> dict[str, Any]:
    """
    Return the per-lap roster for a driver/session, used by the lap-selector UI.

    Each lap entry includes lap number, lap time (seconds), tyre compound, and
    pit-in/out flags so the UI can render context like "Lap 14 — MEDIUM, 1:32.4".
    """
    driver = driver.upper()
    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps.pick_driver(driver)
        if laps.empty:
            return {
                "year": year,
                "event": event,
                "session_type": session_type,
                "driver": driver,
                "laps": [],
                "fastest_lap_number": None,
                "fallback": True,
                "fallback_reason": "No laps found for requested driver/session.",
            }

        fastest_lap_number: int | None = None
        try:
            fastest = laps.pick_fastest()
            if "LapNumber" in fastest and pd.notna(fastest["LapNumber"]):
                fastest_lap_number = int(fastest["LapNumber"])
        except Exception:  # noqa: BLE001 — fastest lap is best-effort metadata
            fastest_lap_number = None

        out: list[dict[str, Any]] = []
        for _, lap in laps.iterrows():
            lap_number = lap.get("LapNumber")
            if pd.isna(lap_number):
                continue
            lap_time_seconds: float | None = None
            lap_time_raw = lap.get("LapTime")
            if lap_time_raw is not None and not pd.isna(lap_time_raw):
                try:
                    lap_time_seconds = float(lap_time_raw.total_seconds())
                except AttributeError:
                    lap_time_seconds = None

            compound = lap.get("Compound")
            compound = str(compound) if compound is not None and not pd.isna(compound) else None

            pit_in = lap.get("PitInTime")
            pit_out = lap.get("PitOutTime")
            out.append({
                "lap_number": int(lap_number),
                "lap_time_seconds": lap_time_seconds,
                "compound": compound,
                "is_pit_in": bool(pit_in is not None and not pd.isna(pit_in)),
                "is_pit_out": bool(pit_out is not None and not pd.isna(pit_out)),
            })

        return {
            "year": year,
            "event": event,
            "session_type": session_type,
            "driver": driver,
            "laps": out,
            "fastest_lap_number": fastest_lap_number,
            "fallback": False,
            "fallback_reason": None,
        }
    except Exception as exc:  # noqa: BLE001 — surface any FastF1 failure to caller
        return {
            "year": year,
            "event": event,
            "session_type": session_type,
            "driver": driver,
            "laps": [],
            "fastest_lap_number": None,
            "fallback": True,
            "fallback_reason": str(exc),
        }


@_ttl_cached(_tyre_features_cache, is_good=lambda r: not r.get("fallback"), name="tyre_features")
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
