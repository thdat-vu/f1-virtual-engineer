"""Tests for the Redis L2 layer added to core.llm (#120).

We patch _ensure_configured so the actual Gemini SDK never runs, and use
fakeredis as the L2 backend so cache writes/hits are observable in CI.

Coverage:
- generate_rationale: L2 hit short-circuits the Gemini call, seeds L1.
- generate_rationale: a fresh compute writes to both tiers.
- generate_rationale: empty response is NOT cached at L2.
- generate_structured: L2 hit short-circuits Gemini, seeds L1.
- generate_structured: corrupt L2 payload behaves like a miss.
- Redis disabled (no REDIS_URL): wrapper still works via L1 only.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import fakeredis

from core import llm as core_llm
from core import redis_cache


def _install_fake_redis() -> fakeredis.FakeRedis:
    fake = fakeredis.FakeRedis()
    redis_cache._client = fake
    redis_cache._init_attempted = True
    return fake


def _make_genai(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    client = MagicMock()
    client.generate_content.return_value = response
    genai = MagicMock()
    genai.GenerativeModel.return_value = client
    return genai


class RationaleL2Tests(unittest.TestCase):
    def setUp(self):
        core_llm._reset_cache_for_tests()
        redis_cache.reset_for_tests()
        self.fake = _install_fake_redis()

    def tearDown(self):
        redis_cache.reset_for_tests()

    def test_l2_hit_skips_gemini_and_seeds_l1(self):
        ctx = {"intent": {"driver": "HAM"}}
        key = core_llm._context_key(ctx)
        # Pre-populate L2 only — L1 is empty.
        redis_cache.set("rationale", key, "cached engineer call", ttl_seconds=600)

        gemini = _make_genai("should not be called")
        with patch.object(core_llm, "_ensure_configured", return_value=gemini):
            result = core_llm.generate_rationale(ctx)

        self.assertEqual(result, "cached engineer call")
        gemini.GenerativeModel.assert_not_called()
        # Seeded L1 — second call uses dict.
        self.assertIn(key, core_llm._cache)

    def test_compute_path_writes_to_both_tiers(self):
        ctx = {"intent": {"driver": "VER"}}
        gemini = _make_genai("Box this lap, Max.")

        with patch.object(core_llm, "_ensure_configured", return_value=gemini):
            result = core_llm.generate_rationale(ctx)

        self.assertEqual(result, "Box this lap, Max.")
        key = core_llm._context_key(ctx)
        self.assertIn(key, core_llm._cache)
        self.assertEqual(redis_cache.get("rationale", key), "Box this lap, Max.")

    def test_empty_response_is_not_cached_at_l2(self):
        ctx = {"intent": {"driver": "NOR"}}
        gemini = _make_genai("   ")

        with patch.object(core_llm, "_ensure_configured", return_value=gemini):
            result = core_llm.generate_rationale(ctx)

        self.assertIsNone(result)
        key = core_llm._context_key(ctx)
        self.assertIsNone(redis_cache.get("rationale", key))


class StructuredL2Tests(unittest.TestCase):
    def setUp(self):
        core_llm._reset_cache_for_tests()
        redis_cache.reset_for_tests()
        self.fake = _install_fake_redis()

    def tearDown(self):
        redis_cache.reset_for_tests()

    def test_l2_hit_skips_gemini(self):
        prompt = "classify radio"
        payload = {"transcript": "box now"}
        key = core_llm._context_key({"prompt": prompt, "payload": payload}, namespace="structured")
        redis_cache.set(
            "structured", key, '{"classification":"strategy_request","severity":"low"}', ttl_seconds=600
        )

        gemini = _make_genai("should not be called")
        with patch.object(core_llm, "_ensure_configured", return_value=gemini):
            result = core_llm.generate_structured(payload, system_prompt=prompt)

        self.assertEqual(result, {"classification": "strategy_request", "severity": "low"})
        gemini.GenerativeModel.assert_not_called()

    def test_corrupt_l2_payload_treated_as_miss(self):
        prompt = "classify radio"
        payload = {"transcript": "tyre gone"}
        key = core_llm._context_key({"prompt": prompt, "payload": payload}, namespace="structured")
        redis_cache.set("structured", key, "{not valid json", ttl_seconds=600)

        gemini = _make_genai('{"classification":"tyre_issue","severity":"high"}')
        with patch.object(core_llm, "_ensure_configured", return_value=gemini):
            result = core_llm.generate_structured(payload, system_prompt=prompt)

        self.assertEqual(result, {"classification": "tyre_issue", "severity": "high"})
        gemini.GenerativeModel.assert_called_once()
        # Compute path overwrote the corrupt entry.
        self.assertEqual(
            redis_cache.get("structured", key),
            '{"classification":"tyre_issue","severity":"high"}',
        )


class RedisDisabledTests(unittest.TestCase):
    def setUp(self):
        core_llm._reset_cache_for_tests()
        redis_cache.reset_for_tests()
        # Do NOT install fakeredis — Redis stays disabled.

    def test_l1_only_path_still_works(self):
        ctx = {"intent": {"driver": "ALO"}}
        gemini = _make_genai("Plan B confirmed.")
        with patch.object(core_llm, "_ensure_configured", return_value=gemini):
            first = core_llm.generate_rationale(ctx)
            second = core_llm.generate_rationale(ctx)

        self.assertEqual(first, "Plan B confirmed.")
        self.assertEqual(second, "Plan B confirmed.")
        # Single Gemini call — second served from L1 dict.
        gemini.GenerativeModel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
