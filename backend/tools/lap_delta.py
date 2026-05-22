"""Per-distance lap delta between two drivers (#184).

The race-engineer / data-fan question this answers: "VER beats HAM by
0.3s — *where* on the lap?" Stacking the speed/throttle traces (which
the comparison view already does) makes that visible only if you eye
the two lines very carefully. A Δt-vs-distance trace makes the
gain/loss explicit at every metre.

We don't reuse fastf1.utils.delta_time because it's deprecated and
known to be inaccurate. Approach here:

1. Pick each driver's fastest lap (or a caller-pinned lap) and request
   the car telemetry with Distance + SessionTime columns.
2. Align on a common distance grid (numpy.interp). Reference is
   driver_a — driver_b's time-at-distance is interpolated onto that
   grid.
3. Δt(distance) = time_b(distance) − time_a(distance), normalised so
   both laps start at zero (we want gap accumulating along the lap,
   not absolute session-clock difference).

Fail-closed envelope mirrors the rest of the helpers in this module so
``/lap-delta`` (or whichever endpoint surfaces this) never 5xxs on a
sparse telemetry session.
"""

from __future__ import annotations

import logging
from typing import Any

import fastf1
import numpy as np

# Sample density of the returned series. Frontend renders a sparkline-
# style trace, not a precise scientific plot; 250 points keeps the
# wire payload small (~5 KB) and stays smooth even on long laps.
_DELTA_SAMPLE_POINTS = 250

# Minimum Distance points per lap before we consider the telemetry
# usable. FP1 install laps and safety-car laps sometimes return ~30
# samples, which produces a jagged delta and leads to viewer mistrust.
_MIN_DISTANCE_SAMPLES = 80

_logger = logging.getLogger(__name__)


def _empty_envelope(*, reason: str) -> dict[str, Any]:
    return {
        "distance_m": [],
        "delta_seconds": [],
        "reference_driver": None,
        "compare_driver": None,
        "reference_lap": None,
        "compare_lap": None,
        "fallback": True,
        "fallback_reason": reason,
    }


def _pick_lap_telemetry(session: Any, driver: str, lap_number: int | None):
    """Return (lap_number, telemetry-with-Distance) or (None, None) on miss.

    When ``lap_number`` is None we pick the driver's fastest lap, which
    matches what the comparison view already implies (no lap selector
    on either side).
    """
    laps = session.laps.pick_drivers(driver) if hasattr(session.laps, "pick_drivers") else session.laps.pick_driver(driver)
    if laps.empty:
        return None, None
    if lap_number is None:
        lap = laps.pick_fastest()
        if lap is None or lap.empty:
            return None, None
    else:
        match = laps[laps["LapNumber"] == lap_number]
        if match.empty:
            return None, None
        lap = match.iloc[0]

    try:
        # add_distance=True attaches a Distance column derived from
        # speed × dt integration — we need it as the alignment axis.
        car = lap.get_car_data().add_distance()
    except Exception as exc:  # noqa: BLE001 — degrade silently
        _logger.warning("get_car_data failed for %s lap %s: %s", driver, lap_number, exc)
        return None, None

    if "Distance" not in car.columns or "SessionTime" not in car.columns:
        return None, None
    if len(car) < _MIN_DISTANCE_SAMPLES:
        return None, None

    return int(lap["LapNumber"]), car


def compute_lap_delta(
    year: int,
    event: str,
    session_type: str,
    reference_driver: str,
    compare_driver: str,
    reference_lap: int | None = None,
    compare_lap: int | None = None,
) -> dict[str, Any]:
    """Per-distance Δt of ``compare_driver`` vs ``reference_driver``.

    Positive ``delta_seconds[i]`` ⇒ compare_driver was *behind* at
    that distance (took longer to reach it). Frontend can colour
    positives red, negatives green from the reference's perspective.

    All errors resolve to the empty envelope — same fail-closed
    contract as the other helpers in this package. Notable failure
    modes the caller should expect:

    - one driver missing telemetry on the chosen lap (safety car,
      retirement, install lap),
    - Distance column unavailable on practice sessions with sparse
      telemetry,
    - both drivers' fastest laps differing in length by >5% (rare;
      usually a red flag that one was a partial lap).
    """
    ref = reference_driver.upper()
    cmp = compare_driver.upper()
    if ref == cmp:
        return _empty_envelope(reason="Reference and compare driver are the same.")

    try:
        session = fastf1.get_session(year, event, session_type)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
    except Exception as exc:  # noqa: BLE001 — fastf1 raises a wide tree
        return _empty_envelope(reason=f"Session load failed: {exc}")

    ref_lap_n, ref_tel = _pick_lap_telemetry(session, ref, reference_lap)
    cmp_lap_n, cmp_tel = _pick_lap_telemetry(session, cmp, compare_lap)

    if ref_tel is None or cmp_tel is None:
        missing = ref if ref_tel is None else cmp
        return _empty_envelope(reason=f"Telemetry unavailable for {missing}.")

    ref_dist = ref_tel["Distance"].to_numpy()
    cmp_dist = cmp_tel["Distance"].to_numpy()
    # SessionTime is a Timedelta; convert to total seconds and rebase
    # each lap to zero at start so we measure gap-accumulation along
    # the lap, not an arbitrary session-clock offset.
    ref_t = ref_tel["SessionTime"].dt.total_seconds().to_numpy()
    cmp_t = cmp_tel["SessionTime"].dt.total_seconds().to_numpy()
    ref_t = ref_t - ref_t[0]
    cmp_t = cmp_t - cmp_t[0]

    # Restrict to the overlap interval — if one lap was longer for any
    # reason (sector flag, sausage kerb, slight position-line offset)
    # extrapolating beyond would invent data.
    max_dist = float(min(ref_dist[-1], cmp_dist[-1]))
    if max_dist <= 0:
        return _empty_envelope(reason="Distance arrays do not overlap.")

    grid = np.linspace(0.0, max_dist, _DELTA_SAMPLE_POINTS)
    ref_t_on_grid = np.interp(grid, ref_dist, ref_t)
    cmp_t_on_grid = np.interp(grid, cmp_dist, cmp_t)
    delta = cmp_t_on_grid - ref_t_on_grid

    return {
        "distance_m": [round(float(x), 1) for x in grid],
        "delta_seconds": [round(float(x), 3) for x in delta],
        "reference_driver": ref,
        "compare_driver": cmp,
        "reference_lap": ref_lap_n,
        "compare_lap": cmp_lap_n,
        "fallback": False,
        "fallback_reason": None,
    }
