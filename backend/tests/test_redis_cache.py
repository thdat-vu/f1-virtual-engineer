"""Tests for the Redis-backed L2 cache (#100 slice D).

Strategy: use ``fakeredis`` as a drop-in for the ``redis`` client so we
can exercise the real ``redis_cache.get`` / ``redis_cache.set`` code path
in CI without provisioning a Redis instance.

Coverage:
- L1 hit short-circuits L2 (no Redis call).
- L1 miss + L2 hit seeds L1.
- L1 miss + L2 miss computes once and writes to both tiers.
- Fallback results never leak into L2.
- A Redis outage degrades silently — the call still succeeds.
- Disabled config (no REDIS_URL) means is_enabled() is False and
  set()/get() are no-ops.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import fakeredis

from core import redis_cache
from tools import fastf1_helper
from tools.fastf1_helper import (
    _reset_caches_for_tests,
    get_event_drivers,
    get_year_schedule,
)


def _install_fake_redis() -> fakeredis.FakeRedis:
    """Wire fakeredis into core.redis_cache so we can write real assertions."""
    fake = fakeredis.FakeRedis()
    redis_cache._client = fake
    redis_cache._init_attempted = True
    return fake


class RedisCacheModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        redis_cache.reset_for_tests()

    def tearDown(self) -> None:
        redis_cache.reset_for_tests()
        os.environ.pop("REDIS_URL", None)

    def test_disabled_by_default(self):
        # No REDIS_URL → is_enabled() False, get/set no-op.
        self.assertFalse(redis_cache.is_enabled())
        self.assertIsNone(redis_cache.get("foo", "bar"))
        redis_cache.set("foo", "bar", {"x": 1}, ttl_seconds=60)  # must not raise

    def test_roundtrip_with_fakeredis(self):
        _install_fake_redis()
        self.assertTrue(redis_cache.is_enabled())
        redis_cache.set("schedule", "abc123", {"year": 2024, "events": []}, ttl_seconds=60)
        self.assertEqual(redis_cache.get("schedule", "abc123"), {"year": 2024, "events": []})
        self.assertIsNone(redis_cache.get("schedule", "missing"))

    def test_redis_failure_is_silent(self):
        # Stub the client so every call raises. The wrapper must not propagate.
        broken = MagicMock()
        broken.get.side_effect = RuntimeError("boom")
        broken.set.side_effect = RuntimeError("boom")
        redis_cache._client = broken
        redis_cache._init_attempted = True
        self.assertIsNone(redis_cache.get("schedule", "x"))
        redis_cache.set("schedule", "x", {"k": 1}, ttl_seconds=60)  # must not raise


class TwoTierLookupTests(unittest.TestCase):
    """Verify the L1 → L2 → compute order in tools/fastf1_helper."""

    def setUp(self) -> None:
        _reset_caches_for_tests()
        self.fake = _install_fake_redis()

    def tearDown(self) -> None:
        redis_cache.reset_for_tests()
        _reset_caches_for_tests()

    def _fake_schedule(self, name: str = "Monza"):
        fake_schedule = MagicMock()
        fake_schedule.iterrows.return_value = iter([
            (0, {"EventName": name, "Location": name, "RoundNumber": 1, "OfficialEventName": "GP"}),
        ])
        return fake_schedule

    def test_compute_writes_through_to_l2(self):
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=self._fake_schedule()) as mock_get:
            get_year_schedule(2024)
        self.assertEqual(mock_get.call_count, 1)
        # L2 should now have the entry under the schedule namespace.
        keys = [k.decode() for k in self.fake.scan_iter("f1:cache:schedule:*")]
        self.assertEqual(len(keys), 1)

    def test_l1_hit_short_circuits_l2(self):
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=self._fake_schedule()):
            get_year_schedule(2024)  # primes L1 + L2

        # Wipe Redis but keep L1 — a subsequent call must still hit and not
        # touch Redis at all. Patch redis_cache.get to assert it's not called.
        with patch.object(redis_cache, "get") as mock_get, \
             patch.object(fastf1_helper.fastf1, "get_event_schedule") as mock_ff1:
            result = get_year_schedule(2024)
        mock_get.assert_not_called()
        mock_ff1.assert_not_called()
        self.assertEqual(result[0]["name"], "Monza")

    def test_l2_hit_after_l1_eviction_skips_compute(self):
        # Compute once so L2 is warm.
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=self._fake_schedule("Imola")):
            get_year_schedule(2025)

        # Simulate process restart: wipe L1 only.
        _reset_caches_for_tests()

        # Now another call must use L2 and never touch fastf1.
        with patch.object(fastf1_helper.fastf1, "get_event_schedule") as mock_ff1:
            result = get_year_schedule(2025)
        mock_ff1.assert_not_called()
        self.assertEqual(result[0]["name"], "Imola")

    def test_fallback_results_not_written_to_l2(self):
        # Make the underlying fastf1 call raise so the helper returns a
        # fallback dict. is_good() should refuse to cache it in either tier.
        with patch.object(fastf1_helper.fastf1, "get_session", side_effect=RuntimeError("net")):
            r = get_event_drivers(year=2024, event="Imola")
        self.assertTrue(r["fallback"])
        keys = [k.decode() for k in self.fake.scan_iter("f1:cache:roster:*")]
        self.assertEqual(keys, [])

    def test_redis_outage_still_computes_and_returns(self):
        # Realistic outage: the underlying client raises on every op.
        # core.redis_cache itself wraps in try/except, so get/set return
        # None / no-op respectively and the helper proceeds to compute.
        broken = MagicMock()
        broken.get.side_effect = RuntimeError("redis down")
        broken.set.side_effect = RuntimeError("redis down")
        redis_cache._client = broken
        redis_cache._init_attempted = True

        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=self._fake_schedule("Spa")) as mock_ff1:
            result = get_year_schedule(2022)
        mock_ff1.assert_called_once()
        self.assertEqual(result[0]["name"], "Spa")


if __name__ == "__main__":
    unittest.main()
