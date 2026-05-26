"""Per-distance lap delta for the SAME driver across two seasons (#229).

Sister to ``tools.lap_delta`` — same alignment math, different question.
The race-engineer / data-fan question this answers: "How much faster
is HAM at Silverstone in 2024 than 2023, and where on the lap does
the new car make up the time?"

Two sessions are loaded independently because they are genuinely
different — different cars, different tyre compounds, sometimes
slightly different track layouts. We compare each driver's fastest
lap from each year, projected onto a shared distance grid.

We deliberately don't reuse `compute_lap_delta` directly: that helper
loads one session and picks two drivers from it. Splitting two-driver
vs cross-year keeps the contracts honest — a `cross_year` flag on
the existing endpoint would have to silently ignore half its fields
for one shape or the other.

Distance alignment caveat: track layouts occasionally change between
years (Spa T1, Silverstone Loop, Australia kerb edits). The shared
distance grid stops at the shorter lap's max distance. Where the
layout differs, the delta there reflects layout difference + pace
difference, not just pace. Surface that to the viewer in the UI
("distance reflects per-year layout").
"""

from __future__ import annotations

import logging
from typing import Any

import fastf1
import numpy as np

# Same constants as the sister helper so wire-payload size and
# minimum-sample-rejection stays consistent across the two endpoints.
_DELTA_SAMPLE_POINTS = 250
_MIN_DISTANCE_SAMPLES = 80

_logger = logging.getLogger(__name__)


def _empty_envelope(*, reason: str) -> dict[str, Any]:
    return {
        "distance_m": [],
        "delta_seconds": [],
        "driver": None,
        "year_a": None,
        "year_b": None,
        "lap_a": None,
        "lap_b": None,
        "lap_time_a_seconds": None,
        "lap_time_b_seconds": None,
        "fallback": True,
        "fallback_reason": reason,
    }


def _pick_fastest_lap_telemetry(session: Any, driver: str):
    """Return (lap_number, lap_time_seconds, telemetry-with-Distance) or all-None.

    Mirrors `tools.lap_delta._pick_lap_telemetry` but always picks the
    fastest lap — cross-year comparison doesn't expose a per-lap
    selector since the two sessions don't share lap numbers in any
    meaningful way.
    """
    laps = (
        session.laps.pick_drivers(driver)
        if hasattr(session.laps, "pick_drivers")
        else session.laps.pick_driver(driver)
    )
    if laps.empty:
        return None, None, None

    lap = laps.pick_fastest()
    if lap is None or lap.empty:
        return None, None, None

    try:
        car = lap.get_car_data().add_distance()
    except Exception as exc:  # noqa: BLE001 — degrade silently
        _logger.warning("get_car_data failed for %s: %s", driver, exc)
        return None, None, None

    if "Distance" not in car.columns or "SessionTime" not in car.columns:
        return None, None, None
    if len(car) < _MIN_DISTANCE_SAMPLES:
        return None, None, None

    lap_time_seconds: float | None = None
    try:
        lap_time = lap["LapTime"]
        if lap_time is not None and not getattr(lap_time, "isnull", lambda: False)():
            lap_time_seconds = float(lap_time.total_seconds())
    except Exception:  # noqa: BLE001 — best-effort, lap_time is cosmetic
        lap_time_seconds = None

    return int(lap["LapNumber"]), lap_time_seconds, car


def compute_cross_year_lap_delta(
    event: str,
    session_type: str,
    driver: str,
    year_a: int,
    year_b: int,
) -> dict[str, Any]:
    """Per-distance Δt of ``driver``'s fastest lap in ``year_b`` vs ``year_a``.

    Positive ``delta_seconds[i]`` ⇒ ``year_b`` lap was *slower* at
    that distance — i.e. the older car was faster there. Frontend
    can colour positives red, negatives green from the year_a
    perspective (same convention as the two-driver delta).

    All errors resolve to the empty envelope. Notable failure modes:

    - one year doesn't have a recorded fastest lap for the driver
      (rookie season, didn't qualify, retirement-on-lap-1),
    - the event slug doesn't resolve in one of the years (calendar
      churn — Mexico GP becomes Mexico City GP, etc.),
    - track layout edits between seasons producing wildly different
      distance arrays. Caller should still render but flag in copy.
    """
    drv = driver.upper()

    if year_a == year_b:
        return _empty_envelope(
            reason="year_a and year_b are the same; use /lap-delta for same-session compare.",
        )

    try:
        session_a = fastf1.get_session(year_a, event, session_type)
        session_a.load(laps=True, telemetry=True, weather=False, messages=False)
    except Exception as exc:  # noqa: BLE001
        return _empty_envelope(reason=f"Session load failed for {year_a}: {exc}")

    try:
        session_b = fastf1.get_session(year_b, event, session_type)
        session_b.load(laps=True, telemetry=True, weather=False, messages=False)
    except Exception as exc:  # noqa: BLE001
        return _empty_envelope(reason=f"Session load failed for {year_b}: {exc}")

    lap_a_n, lap_time_a, tel_a = _pick_fastest_lap_telemetry(session_a, drv)
    lap_b_n, lap_time_b, tel_b = _pick_fastest_lap_telemetry(session_b, drv)

    if tel_a is None or tel_b is None:
        missing_year = year_a if tel_a is None else year_b
        return _empty_envelope(
            reason=f"Telemetry unavailable for {drv} in {missing_year}.",
        )

    dist_a = tel_a["Distance"].to_numpy()
    dist_b = tel_b["Distance"].to_numpy()
    t_a = tel_a["SessionTime"].dt.total_seconds().to_numpy()
    t_b = tel_b["SessionTime"].dt.total_seconds().to_numpy()
    t_a = t_a - t_a[0]
    t_b = t_b - t_b[0]

    max_dist = float(min(dist_a[-1], dist_b[-1]))
    if max_dist <= 0:
        return _empty_envelope(reason="Distance arrays do not overlap.")

    grid = np.linspace(0.0, max_dist, _DELTA_SAMPLE_POINTS)
    t_a_on_grid = np.interp(grid, dist_a, t_a)
    t_b_on_grid = np.interp(grid, dist_b, t_b)
    delta = t_b_on_grid - t_a_on_grid

    return {
        "distance_m": [round(float(x), 1) for x in grid],
        "delta_seconds": [round(float(x), 3) for x in delta],
        "driver": drv,
        "year_a": int(year_a),
        "year_b": int(year_b),
        "lap_a": lap_a_n,
        "lap_b": lap_b_n,
        "lap_time_a_seconds": round(lap_time_a, 3) if lap_time_a is not None else None,
        "lap_time_b_seconds": round(lap_time_b, 3) if lap_time_b is not None else None,
        "fallback": False,
        "fallback_reason": None,
    }
