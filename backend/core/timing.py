"""Lightweight request-timing instrumentation.

Goal: give us a baseline before optimizing FastF1 latency (#100). We need to
know which routes are slow and by how much *before* touching threadpools,
caching, or parquet pre-bakes, so that any subsequent perf PR can quote
a real before/after delta.

Design:
- A FastAPI middleware (``TimingMiddleware``) wraps every request, measures
  wall-clock duration, stamps an ``X-Process-Time`` response header (ms,
  rounded to 0.1ms), and pushes the duration into an in-memory ring buffer
  keyed by ``"METHOD route-template"`` (the matched APIRoute path, so
  ``/events/{year}`` is grouped regardless of the actual year).
- A ``GET /metrics`` handler reads the buffer and computes p50/p95/max
  per route. Pure stdlib, no Prometheus dep.
- ``METRICS_ENABLED=false`` disables both the header and the buffer; useful
  for tests that assert on response headers in a stricter setup, or for
  prod once we move to a real metrics pipeline.

Limits (intentional):
- Single process only — multi-worker would need Redis or a shared backend.
- Last 50 samples per route; older drop off. p95 on 50 samples is noisy
  but the deltas we care about (3s → 300ms) dwarf the noise.
- No trace spans, no per-user breakdown, no histograms. v1.
"""

from __future__ import annotations

import os
import time
from collections import deque
from statistics import quantiles
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match


_SAMPLE_CAP = 50
_buffers: dict[str, deque[float]] = {}


def _is_enabled() -> bool:
    return os.environ.get("METRICS_ENABLED", "true").lower() != "false"


def _route_key(request: Request) -> str:
    """Group by matched route template so ``/events/2024`` and ``/events/2023``
    collapse into ``"GET /events/{year}"``. Falls back to the raw path for
    unmatched routes (404s)."""
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL and hasattr(route, "path"):
            return f"{request.method} {route.path}"
    return f"{request.method} {request.url.path}"


def _record(route: str, duration_s: float) -> None:
    buf = _buffers.get(route)
    if buf is None:
        buf = deque(maxlen=_SAMPLE_CAP)
        _buffers[route] = buf
    buf.append(duration_s)


def _percentile(samples: Iterable[float], pct: float) -> float:
    """Return the ``pct``-th percentile (0..1) in seconds.

    statistics.quantiles needs at least 2 points; for 1 sample we just
    return it. Returns the sample itself rather than interpolating to
    keep p95 on tiny buffers sane.
    """
    data = sorted(samples)
    if not data:
        return 0.0
    if len(data) == 1:
        return data[0]
    # n=100 means quantiles returns 99 cut points: index 49 = p50, 94 = p95.
    cuts = quantiles(data, n=100, method="inclusive")
    idx = max(0, min(98, int(round(pct * 100)) - 1))
    return cuts[idx]


def snapshot_metrics() -> dict[str, dict[str, float | int]]:
    """Build the JSON payload the /metrics endpoint returns."""
    out: dict[str, dict[str, float | int]] = {}
    for route, buf in _buffers.items():
        if not buf:
            continue
        samples = list(buf)
        out[route] = {
            "count": len(samples),
            "p50_ms": round(_percentile(samples, 0.50) * 1000, 1),
            "p95_ms": round(_percentile(samples, 0.95) * 1000, 1),
            "max_ms": round(max(samples) * 1000, 1),
            "last_ms": round(samples[-1] * 1000, 1),
        }
    return out


def reset_metrics_for_tests() -> None:
    _buffers.clear()


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _is_enabled():
            return await call_next(request)
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start
        try:
            route = _route_key(request)
            _record(route, elapsed)
        except Exception:  # noqa: BLE001 — never break a response on metrics
            pass
        response.headers["X-Process-Time"] = f"{elapsed * 1000:.1f}"
        return response
