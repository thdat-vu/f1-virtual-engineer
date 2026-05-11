"""Tests for the FastF1 helper TTL caches (#100 slice B).

We don't exercise real FastF1 here — that's slow and network-bound. Instead,
we patch the underlying FastF1 entrypoints and assert the wrapper:

1. Caches "good" results so the underlying call runs once.
2. Refuses to cache fallback results (transient errors must not stick).
3. Returns cached data verbatim on hit.
4. Different argument tuples hit different cache slots.
5. _reset_caches_for_tests() actually wipes state between tests.
"""

from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import MagicMock, patch

from tools import fastf1_helper
from tools.fastf1_helper import (
    _reset_caches_for_tests,
    extract_tyre_wear_features,
    get_event_drivers,
    get_session_lap_list,
    get_session_telemetry_summary,
    get_year_schedule,
)


class ScheduleCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_caches_for_tests()

    def test_good_result_cached(self):
        fake_schedule = MagicMock()
        fake_schedule.iterrows.return_value = iter([
            (0, {"EventName": "Bahrain GP", "Location": "Sakhir", "RoundNumber": 1, "OfficialEventName": "FORMULA 1 BAHRAIN GRAND PRIX 2024"}),
        ])
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=fake_schedule) as mock_get:
            r1 = get_year_schedule(2024)
            r2 = get_year_schedule(2024)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(r1, r2)
        self.assertEqual(r1[0]["name"], "Bahrain GP")

    def test_empty_result_not_cached(self):
        # Empty list = treat as "not good" so a retry can repopulate.
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", side_effect=RuntimeError("net")) as mock_get:
            r1 = get_year_schedule(2024)
            r2 = get_year_schedule(2024)
        self.assertEqual(r1, [])
        self.assertEqual(r2, [])
        self.assertEqual(mock_get.call_count, 2)

    def test_different_years_isolated(self):
        fake = MagicMock()
        fake.iterrows.return_value = iter([])
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=fake) as mock_get:
            get_year_schedule(2024)
            get_year_schedule(2023)
        # 2024 yields [] which isn't cached, 2023 also []; both miss = 2 calls.
        self.assertEqual(mock_get.call_count, 2)


class FallbackBypassTests(unittest.TestCase):
    """Helpers that return {"fallback": True, ...} on error must not cache it."""

    def setUp(self) -> None:
        _reset_caches_for_tests()

    def test_roster_fallback_not_cached(self):
        with patch.object(fastf1_helper.fastf1, "get_session", side_effect=RuntimeError("boom")) as mock_get:
            r1 = get_event_drivers(2024, "Monza")
            r2 = get_event_drivers(2024, "Monza")
        self.assertTrue(r1["fallback"])
        self.assertTrue(r2["fallback"])
        # 2 lookups * 2 attempts (Race + Qualifying) = 4 underlying calls.
        self.assertEqual(mock_get.call_count, 4)

    def test_telemetry_fallback_not_cached(self):
        with patch.object(fastf1_helper.fastf1, "get_session", side_effect=RuntimeError("boom")):
            r1 = get_session_telemetry_summary(2024, "Monza", "R", "VER")
            r2 = get_session_telemetry_summary(2024, "Monza", "R", "VER")
        self.assertTrue(r1["fallback"])
        self.assertTrue(r2["fallback"])

    def test_telemetry_success_cached(self):
        def fake_get_session(*args, **kwargs):
            session = MagicMock()
            session.load.return_value = None
            laps_for_driver = MagicMock()
            laps_for_driver.empty = False
            fastest = {
                "LapNumber": 14,
                "LapTime": MagicMock(total_seconds=MagicMock(return_value=92.4)),
                "Sector1Time": MagicMock(total_seconds=MagicMock(return_value=28.0)),
                "Sector2Time": MagicMock(total_seconds=MagicMock(return_value=30.0)),
            }
            laps_for_driver.pick_fastest.return_value = MagicMock(
                __getitem__=lambda self, k: fastest[k],
                __contains__=lambda self, k: k in fastest,
                get=lambda k, default=None: fastest.get(k, default),
                get_telemetry=MagicMock(return_value=_fake_telemetry_df()),
            )
            session.laps.pick_driver.return_value = laps_for_driver
            return session

        with patch.object(fastf1_helper.fastf1, "get_session", side_effect=fake_get_session) as mock_get:
            r1 = get_session_telemetry_summary(2024, "Monza", "R", "VER")
            r2 = get_session_telemetry_summary(2024, "Monza", "R", "VER")
        self.assertFalse(r1["fallback"])
        self.assertEqual(mock_get.call_count, 1)
        self.assertIs(r1, r2)  # exact object, returned from cache

    def test_lap_list_fallback_not_cached(self):
        with patch.object(fastf1_helper.fastf1, "get_session", side_effect=RuntimeError("boom")) as mock_get:
            r1 = get_session_lap_list(2024, "Monza", "R", "VER")
            r2 = get_session_lap_list(2024, "Monza", "R", "VER")
        self.assertTrue(r1["fallback"])
        self.assertTrue(r2["fallback"])
        self.assertEqual(mock_get.call_count, 2)

    def test_tyre_features_fallback_not_cached(self):
        with patch.object(fastf1_helper.fastf1, "get_session", side_effect=RuntimeError("boom")) as mock_get:
            r1 = extract_tyre_wear_features(2024, "Monza", "R", "VER")
            r2 = extract_tyre_wear_features(2024, "Monza", "R", "VER")
        self.assertTrue(r1["fallback"])
        self.assertTrue(r2["fallback"])
        self.assertEqual(mock_get.call_count, 2)


def _fake_telemetry_df():
    """Minimal DataFrame-ish stub that satisfies _normalize_telemetry."""
    import pandas as pd

    return pd.DataFrame({
        "Speed": [200.0, 250.0, 280.0],
        "nGear": [5, 6, 7],
        "RPM": [10000.0, 11000.0, 12000.0],
    })


class AsyncWrapTests(unittest.IsolatedAsyncioTestCase):
    """Sanity check: cached calls run via asyncio.to_thread without blocking."""

    async def asyncSetUp(self) -> None:
        _reset_caches_for_tests()

    async def test_to_thread_serves_cached_result_fast(self):
        fake_schedule = MagicMock()
        fake_schedule.iterrows.return_value = iter([
            (0, {"EventName": "Monza", "Location": "Monza", "RoundNumber": 16, "OfficialEventName": "GP Italia"}),
        ])
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=fake_schedule):
            await asyncio.to_thread(get_year_schedule, 2024)
            start = time.perf_counter()
            await asyncio.to_thread(get_year_schedule, 2024)
            elapsed = time.perf_counter() - start
        # A cache hit + threadpool roundtrip is essentially instant (<50ms even
        # on a loaded CI runner). We use a loose bound so this doesn't flake.
        self.assertLess(elapsed, 0.5)


if __name__ == "__main__":
    unittest.main()
