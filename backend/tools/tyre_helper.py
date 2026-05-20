"""Tyre intelligence helper (#167).

Composes ``predict_tyre_wear`` (lap-time decay, stint progress) with the
already-cached ``get_event_laps`` roster (compound + per-lap data) to
return a *single, frontend-friendly snapshot* of tyre context.

Why a separate module: the strategy graph already calls
``predict_tyre_wear``; tyre intelligence is a peer surface — it answers
"how is this stint actually decaying right now" without needing the
full strategy recommendation. Keeping it next to ``strategy_helper``
reuses the same fail-closed envelope shape.
"""

from __future__ import annotations

from typing import Any

from tools.fastf1_helper import get_session_lap_list
from tools.strategy_helper import predict_tyre_wear


def _empty_envelope(
    *, year: int, event: str, session_type: str, driver: str, reason: str
) -> dict[str, Any]:
    return {
        "driver": driver.upper(),
        "year": year,
        "event": event,
        "session_type": session_type,
        "fallback": True,
        "fallback_reason": reason,
        "compound": None,
        "stint_laps": 0,
        "decay_seconds_per_lap": 0.0,
        "cliff_lap_estimate": None,
        "confidence_band": "low",
    }


def _last_stint_compound(laps: list[dict[str, Any]]) -> tuple[str | None, int]:
    """Walk the lap roster backwards to find the current compound + stint length.

    A stint ends on a pit-in lap — but the compound on the *next* lap
    (pit-out) is the one we care about. So we walk from the last lap
    back, count laps in the trailing run, and stop when we hit a
    pit-in (the lap *after* a pit-in starts a fresh stint).
    """
    if not laps:
        return None, 0

    stint_laps = 0
    compound: str | None = None
    for lap in reversed(laps):
        # First non-empty compound from the tail wins; we keep walking
        # until we see a pit-in to count the stint length.
        if compound is None and lap.get("compound"):
            compound = lap["compound"]
        if lap.get("is_pit_in"):
            break
        stint_laps += 1
    return compound, stint_laps


def _cliff_lap_estimate(
    *, decay_per_lap: float, stint_laps: int, drop_window_laps: list[int]
) -> int | None:
    """Project when the pace cliff hits.

    Two signals to fuse:
    - ``decay_per_lap`` — observed slope; high values mean we're closer to the cliff.
    - ``drop_window_laps`` — heuristic window from ``predict_tyre_wear`` (e.g. ``[8, 14]``).

    A naive estimator: cliff lands at the *start* of the predicted drop
    window, measured from the start of the current stint. If we already
    burned more laps than the window, the cliff is "now" (return
    ``stint_laps`` so the UI can flag immediate degradation).

    Returns ``None`` when we can't make a confident call (degenerate
    inputs) — the UI should hide the cliff line in that case.
    """
    if not drop_window_laps or len(drop_window_laps) < 1:
        return None
    cliff_offset = int(drop_window_laps[0])
    if cliff_offset <= 0:
        return None
    if stint_laps >= cliff_offset:
        # Cliff already reached or passed; surface "now".
        return stint_laps
    # Floor at the heuristic window; decay slope nudges it earlier when steep.
    if decay_per_lap >= 0.45:
        cliff_offset = max(1, cliff_offset - 2)
    elif decay_per_lap >= 0.25:
        cliff_offset = max(1, cliff_offset - 1)
    return cliff_offset


def compute_tyre_decay(
    year: int,
    event: str,
    session_type: str,
    driver: str,
) -> dict[str, Any]:
    """Return a tyre-intelligence snapshot for ``driver``.

    Output shape (also the API contract for ``POST /tyre/analyze``):

    - ``compound`` — current/last stint compound, ``None`` on fallback.
    - ``stint_laps`` — laps completed in the current stint (post last pit).
    - ``decay_seconds_per_lap`` — observed lap-time slope (≥ 0).
    - ``cliff_lap_estimate`` — projected lap when pace drops, or ``None``.
    - ``confidence_band`` — passed through from ``predict_tyre_wear``.
    - ``fallback`` / ``fallback_reason`` — fail-closed metadata.

    Fail-closed: every error path resolves to a populated envelope with
    ``fallback=True`` so callers never need to special-case missing
    data. ``/tyre/analyze`` must never 5xx because of FastF1 hiccups —
    same contract as ``/telemetry``.
    """
    prediction = predict_tyre_wear(year, event, session_type, driver)
    if prediction.get("fallback"):
        return _empty_envelope(
            year=year,
            event=event,
            session_type=session_type,
            driver=driver,
            reason=prediction.get("fallback_reason") or "Tyre features unavailable.",
        )

    pred = prediction["prediction"]
    decay = float(pred["degradation_rate_seconds_per_lap"])
    drop_window = pred.get("expected_performance_drop_window_laps") or []
    confidence = pred.get("confidence_band", "low")

    # Compound + stint length come from the lap roster, which is its own
    # cache and its own fallback path. If it 503s we still have the
    # prediction — surface it without compound rather than blank the
    # whole card.
    compound: str | None = None
    stint_laps: int = 0
    try:
        roster = get_session_lap_list(year, event, session_type, driver)
        if not roster.get("fallback"):
            compound, stint_laps = _last_stint_compound(roster.get("laps") or [])
    except Exception:  # noqa: BLE001 — degrade silently
        compound, stint_laps = None, 0

    cliff = _cliff_lap_estimate(
        decay_per_lap=decay,
        stint_laps=stint_laps,
        drop_window_laps=drop_window,
    )

    return {
        "driver": driver.upper(),
        "year": year,
        "event": event,
        "session_type": session_type,
        "fallback": False,
        "fallback_reason": None,
        "compound": compound,
        "stint_laps": int(stint_laps),
        "decay_seconds_per_lap": round(decay, 4),
        "cliff_lap_estimate": int(cliff) if cliff is not None else None,
        "confidence_band": confidence,
    }
