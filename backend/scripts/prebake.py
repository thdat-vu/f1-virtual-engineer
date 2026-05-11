"""Pre-bake FastF1 helper results to disk (slice C of #100).

Run this once after pulling fresh code so the first user after a restart
gets warm-cache latency on the demo flow instead of paying the multi-
second FastF1 cold-load wall.

Usage:
    cd backend
    FASTF1_PREBAKE_WRITE=true python3 -m scripts.prebake

What it does:
    - Calls the five FastF1 helpers for a small DEMO_SESSIONS list.
    - The decorator in tools.fastf1_helper writes each successful result
      to backend/data/prebake/<helper>/<sha256>.json.gz.
    - On the next server start, the lifespan hook loads those files into
      the in-process TTLCaches.

Add new sessions by appending to DEMO_SESSIONS below. Keep the list
small — every entry costs one real FastF1 session load (~5-30s).
"""

from __future__ import annotations

import os
import sys
import time

# Make `backend/` importable when run as `python3 -m scripts.prebake`.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# The recording flag must be set *before* importing the helpers so the
# decorator captures it. We force it on here so users don't need to
# remember the env var. (Setting it again is a no-op.)
os.environ["FASTF1_PREBAKE_WRITE"] = "true"

from tools.fastf1_helper import (  # noqa: E402 — after env var
    PREBAKE_DIR,
    extract_tyre_wear_features,
    get_event_drivers,
    get_session_lap_list,
    get_session_telemetry_summary,
    get_year_schedule,
)


# Edit this list to pre-bake more sessions. Each entry triggers up to
# four FastF1 loads (roster, lap_list, telemetry, tyre_features). The
# schedule for each year is baked once.
DEMO_SESSIONS: list[dict] = [
    {"year": 2024, "event": "Monza", "session_type": "R", "driver": "VER"},
    {"year": 2024, "event": "Monza", "session_type": "R", "driver": "HAM"},
    {"year": 2024, "event": "Monza", "session_type": "R", "driver": "LEC"},
]


def _safe(label: str, fn, *args, **kwargs) -> tuple[bool, str]:
    start = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return False, f"{label}: raised {exc!r}"
    elapsed = time.perf_counter() - start
    if isinstance(result, dict) and result.get("fallback"):
        return False, f"{label}: fallback — {result.get('fallback_reason')} ({elapsed:.1f}s)"
    if isinstance(result, list) and not result:
        return False, f"{label}: empty result ({elapsed:.1f}s)"
    return True, f"{label}: ok ({elapsed:.1f}s)"


def main() -> int:
    print(f"Writing pre-baked snapshots to: {PREBAKE_DIR}")

    years = sorted({s["year"] for s in DEMO_SESSIONS})
    for year in years:
        ok, msg = _safe(f"schedule {year}", get_year_schedule, year)
        print(("  ✓ " if ok else "  ✗ ") + msg)

    seen_events: set[tuple[int, str]] = set()
    for s in DEMO_SESSIONS:
        year, event = s["year"], s["event"]
        if (year, event) not in seen_events:
            ok, msg = _safe(
                f"roster {year} {event}",
                get_event_drivers,
                year=year,
                event=event,
            )
            print(("  ✓ " if ok else "  ✗ ") + msg)
            seen_events.add((year, event))

        st, driver = s["session_type"], s["driver"]
        ok, msg = _safe(
            f"lap_list {year} {event} {st} {driver}",
            get_session_lap_list,
            year=year,
            event=event,
            session_type=st,
            driver=driver,
        )
        print(("  ✓ " if ok else "  ✗ ") + msg)

        ok, msg = _safe(
            f"telemetry {year} {event} {st} {driver} (fastest)",
            get_session_telemetry_summary,
            year=year,
            event=event,
            session_type=st,
            driver=driver,
            lap_number=None,
        )
        print(("  ✓ " if ok else "  ✗ ") + msg)

        ok, msg = _safe(
            f"tyre_features {year} {event} {st} {driver}",
            extract_tyre_wear_features,
            year=year,
            event=event,
            session_type=st,
            driver=driver,
        )
        print(("  ✓ " if ok else "  ✗ ") + msg)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
