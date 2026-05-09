import pytest

from tests._helpers import reset_rate_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # slowapi keeps an in-memory token bucket per (route, key). Without a reset
    # between tests, a noisy test can leak burst counters into the next one.
    reset_rate_limiter()
    yield
    reset_rate_limiter()
