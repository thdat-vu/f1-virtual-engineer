"""Per-track pit-loss table + undercut math (#168 slice 1C).

Pit-loss = the seconds you give back to the field when you make a pit
stop. It's the sum of (slow zone in entry) + (stationary time) +
(slow zone in exit), measured against the lap time of a car staying
out. F1 teams calibrate this per-track ahead of every race; the
values below are standard approximations within ~1s.

The strategy panel uses pit-loss to convert a raw gap into the more
actionable "undercut viable in N laps" framing. The math is in
``estimate_undercut_break_even_laps`` — see the docstring.

This is hand-curated, not derived from FastF1. We could compute it
from in/out lap differentials but that needs a session.load() with
telemetry and adds variance from individual stop quality. A static
table is good enough for an MVP demo and reduces FastF1 surface area.
"""

from __future__ import annotations

import math


# Source: rough team estimates from race-weekend coverage; precise to
# within ~1s. Keys are uppercased substrings matched against the
# FastF1 event name (e.g. "Japanese Grand Prix" matches "JAPAN").
# Note: keys must be substrings of the actual FastF1 event names.
# "CANADIAN" not "CANADA", "SPANISH" not "SPAIN", "BRITISH" not
# "BRITAIN" — the events are named with the adjective form.
_PIT_LOSS_BY_KEYWORD: dict[str, float] = {
    "BAHRAIN": 22.0,
    "SAUDI": 21.0,
    "AUSTRALIA": 22.0,
    "JAPAN": 22.0,
    "CHINA": 22.0,
    "MIAMI": 21.0,
    "EMILIA": 22.0,
    "MONACO": 17.5,
    "CANADIAN": 16.5,
    "SPANISH": 22.0,
    "AUSTRIA": 19.5,
    "BRITISH": 22.0,
    "HUNGARY": 20.0,
    "BELGIAN": 21.0,
    "DUTCH": 22.0,
    "ITALIAN": 22.0,
    "AZERBAIJAN": 18.5,
    "SINGAPORE": 26.0,
    "UNITED STATES": 22.0,
    "MEXICO": 21.0,
    "BRAZIL": 22.0,
    "LAS VEGAS": 22.0,
    "QATAR": 24.0,
    "ABU DHABI": 20.5,
}

DEFAULT_PIT_LOSS_SECONDS = 22.0
"""Sane default when the event name doesn't match anything in the table.
22s is the median of the curated values — picking it bounds estimation
error to ~5s on either side, which still lets the UI render *something*
useful (the band/order of magnitude) rather than blanking out."""

# Fresh tyres are typically ~0.5s/lap faster than old ones independent
# of any wear degradation we already capture. Capping per-lap advantage
# below this would let degradation=0 cases project undercut_laps→infinity.
_BASELINE_FRESH_TYRE_ADVANTAGE = 0.5

# How many laps the rival typically stays out after seeing us pit. ~3
# laps is a reasonable race-engineer default: ~1 to confirm the threat,
# ~1 to call it, ~1 for the driver to actually box. Used to project the
# *net* gain of an undercut over a realistic settling window rather
# than the instantaneous break-even.
_UNDERCUT_REACTION_WINDOW_LAPS = 3


def lookup_pit_loss_seconds(event: str | None) -> float:
    """Return the pit-loss for ``event`` in seconds, or the default.

    Matches by uppercased keyword substring so "Japanese Grand Prix",
    "Japan GP", and "JAPAN" all resolve to 22.0. Returns the table's
    default when nothing matches — never raises, never returns None.
    """
    if not event:
        return DEFAULT_PIT_LOSS_SECONDS
    needle = event.upper()
    for keyword, seconds in _PIT_LOSS_BY_KEYWORD.items():
        if keyword in needle:
            return seconds
    return DEFAULT_PIT_LOSS_SECONDS


def estimate_undercut_break_even_laps(
    *,
    gap_seconds: float,
    degradation_per_lap: float,
) -> int | None:
    """How many laps before the rival's delayed pit makes the undercut win.

    Classic undercut framing: I pit now, emerging behind. Each lap they
    delay their stop, I gain ``undercut_advantage_per_lap`` seconds on
    them — that's roughly the tyre-degradation slope plus the ~0.5s/lap
    fresh-tyre warmup bonus. If they delay long enough that my gain
    exceeds the current gap, I jump ahead at their stop. So:

        break_even_laps = ceil(gap / advantage_per_lap)

    Returns ``None`` when gap is non-positive (already ahead) or when
    advantage_per_lap is too small to converge — the UI hides the line
    in those cases rather than showing a misleadingly large number.
    """
    if gap_seconds <= 0:
        return None
    advantage = max(degradation_per_lap + _BASELINE_FRESH_TYRE_ADVANTAGE, 0.0)
    if advantage < _BASELINE_FRESH_TYRE_ADVANTAGE * 0.5:
        return None
    laps = math.ceil(gap_seconds / advantage)
    return max(1, laps)


def estimate_expected_undercut_gain_seconds(
    *,
    gap_seconds: float,
    degradation_per_lap: float,
    reaction_window_laps: int = _UNDERCUT_REACTION_WINDOW_LAPS,
) -> float | None:
    """Net seconds gained if I undercut now and rival reacts in ~3 laps.

    Companion to ``estimate_undercut_break_even_laps``. Break-even tells
    you *when* the undercut crosses parity; this tells you *how much*
    you're ahead once everyone settles. The race-engineer question this
    answers: "is this worth doing, or am I just trading positions?"

    Math: over the reaction window I gain ``advantage_per_lap`` per lap
    on the rival. They erase ``gap_seconds`` of cushion when they pit
    later. Net at the moment they emerge:

        net_gain = (reaction_laps × advantage_per_lap) − gap_seconds

    Returns ``None`` when net_gain is non-positive (gap too large for
    the reaction window to overcome) — the UI hides the line so we
    don't show a "gain ~-0.4s" callout that contradicts the green
    "undercut viable" framing above it.
    """
    if gap_seconds <= 0:
        return None
    advantage = max(degradation_per_lap + _BASELINE_FRESH_TYRE_ADVANTAGE, 0.0)
    if advantage < _BASELINE_FRESH_TYRE_ADVANTAGE * 0.5:
        return None
    net_gain = reaction_window_laps * advantage - gap_seconds
    if net_gain <= 0:
        return None
    return round(net_gain, 2)
