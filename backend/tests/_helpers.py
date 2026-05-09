"""Shared test helpers usable by both pytest and unittest."""

from app.main import limiter


def reset_rate_limiter() -> None:
    """Drop slowapi's in-memory token buckets.

    Called from pytest's autouse fixture and from unittest setUp methods,
    so neither runner's tests pollute one another's burst counters.
    """
    limiter.reset()
