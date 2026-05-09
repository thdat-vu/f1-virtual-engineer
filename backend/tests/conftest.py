import pytest

from tests._helpers import force_template_rationale, reset_rate_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # slowapi keeps an in-memory token bucket per (route, key). Without a reset
    # between tests, a noisy test can leak burst counters into the next one.
    reset_rate_limiter()
    yield
    reset_rate_limiter()


@pytest.fixture(autouse=True)
def _default_template_rationale(monkeypatch):
    # Tests that need the LLM path opt in explicitly by re-patching
    # `agents.race_engineer.generate_rationale`. Default is template — so
    # legacy tests asserting on the f-string output still pass regardless of
    # whether GEMINI_API_KEY is set in the environment.
    force_template_rationale(monkeypatch)
    yield

