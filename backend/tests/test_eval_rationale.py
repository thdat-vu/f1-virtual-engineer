"""LLM rationale eval harness (#122).

These tests run real Gemini calls — they are SKIPPED unless the harness is
explicitly opted into. Two conditions must hold for the eval to run:

- ``RUN_LLM_EVAL=1`` in the environment (opt-in flag),
- ``GEMINI_API_KEY`` is present.

CI does NOT set ``RUN_LLM_EVAL``, so the eval never burns API quota in CI
even if a Gemini key leaks into the test environment.

Locally:

    RUN_LLM_EVAL=1 python3 -m pytest backend/tests/test_eval_rationale.py -v

Each fixture asserts:
- every entry in ``expected_substrings`` appears (case-insensitive) in the
  generated rationale,
- no entry in ``forbidden_substrings`` appears (case-insensitive),
- the call returns a non-empty string (the LLM path actually fired).

Add a new case by appending to ``backend/evals/cases/rationale_fixtures.py``
— the harness picks it up automatically via parametrize.
"""

from __future__ import annotations

import os
import unittest

try:
    import pytest  # type: ignore
    _HAS_PYTEST = True
except ImportError:
    # The repo ships two test runners (pytest + unittest discover). The
    # unittest runner doesn't carry pytest as a dep, so we degrade the
    # parametrized eval to a hard skip rather than crashing on import.
    _HAS_PYTEST = False

from core import llm as core_llm
from evals.cases.rationale_fixtures import FIXTURES


def _eval_enabled() -> bool:
    return os.environ.get("RUN_LLM_EVAL") == "1" and bool(os.environ.get("GEMINI_API_KEY"))


if _HAS_PYTEST:
    @pytest.mark.skipif(
        not _eval_enabled(),
        reason="LLM eval harness is opt-in: set RUN_LLM_EVAL=1 and GEMINI_API_KEY to run.",
    )
    @pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f["name"])
    def test_rationale_fixture(fixture):
        # Drop both cache tiers so a previous fixture's cached output cannot
        # accidentally satisfy a different fixture's expected/forbidden lists.
        core_llm._reset_cache_for_tests()

        text = core_llm.generate_rationale(fixture["context"])
        assert text, f"generate_rationale returned no text for {fixture['name']!r}"
        assert isinstance(text, str)

        haystack = text.lower()
        for needle in fixture.get("expected_substrings", []):
            assert needle.lower() in haystack, (
                f"{fixture['name']}: expected substring {needle!r} missing from rationale: {text!r}"
            )
        for forbidden in fixture.get("forbidden_substrings", []):
            assert forbidden.lower() not in haystack, (
                f"{fixture['name']}: forbidden substring {forbidden!r} present in rationale: {text!r}"
            )


class HarnessSmokeTests(unittest.TestCase):
    """Cheap structural checks that always run (no API key required)."""

    def test_fixtures_are_well_formed(self):
        self.assertGreaterEqual(len(FIXTURES), 5, "need at least 5 eval cases")
        seen_names: set[str] = set()
        for fx in FIXTURES:
            for key in ("name", "context", "expected_substrings", "forbidden_substrings"):
                self.assertIn(key, fx, f"fixture missing {key!r}")
            self.assertNotIn(fx["name"], seen_names, f"duplicate fixture name {fx['name']!r}")
            seen_names.add(fx["name"])
            self.assertIsInstance(fx["expected_substrings"], list)
            self.assertIsInstance(fx["forbidden_substrings"], list)
            self.assertTrue(fx["expected_substrings"], f"{fx['name']}: expected_substrings is empty")
            self.assertIn("intent", fx["context"])
