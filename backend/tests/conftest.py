import pytest

from app.main import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # slowapi keeps an in-memory token bucket per (route, key). Without a reset
    # between tests, a noisy test can leak burst counters into the next one.
    limiter.reset()
    yield
    limiter.reset()
