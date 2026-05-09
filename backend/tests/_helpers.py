"""Shared test helpers usable by both pytest and unittest."""

from app.main import limiter
from agents import race_engineer
from core import llm as core_llm


def reset_rate_limiter() -> None:
    """Drop slowapi's in-memory token buckets.

    Called from pytest's autouse fixture and from unittest setUp methods,
    so neither runner's tests pollute one another's burst counters.
    """
    limiter.reset()


def force_template_rationale(monkeypatch=None) -> None:
    """Force ``format_response_node`` onto its deterministic template path.

    Without this, tests that assert on literal template strings would flake
    whenever a real GEMINI_API_KEY is in the environment (returns LLM text)
    or whenever the cached LLM result from an earlier test bleeds through.
    Pytest tests can pass ``monkeypatch`` and undo happens automatically;
    unittest setUp can call without args and rely on the implicit reset.
    """
    core_llm._reset_cache_for_tests()
    if monkeypatch is not None:
        monkeypatch.setattr(race_engineer, "generate_rationale", lambda *_a, **_k: None)
    else:
        race_engineer.generate_rationale = lambda *_a, **_k: None  # type: ignore[assignment]

