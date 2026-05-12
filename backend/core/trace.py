"""Per-request tool-timing trace collected via contextvars.

Pattern:
- The /analyze handler (or agent entrypoint) calls ``start_trace()`` before
  dispatching work, then ``get_trace()`` after to read the list back.
- Tools decorated with ``@traced("name")`` push one entry per invocation
  into whatever list is bound in the current context — or a no-op when no
  trace is active (e.g. unit tests calling the tool directly).

contextvars copy across ``asyncio.to_thread`` and ``asyncio.create_task``
since Python 3.7, so threaded tool calls inside the agent still see the
request-scoped list.
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, TypeVar


_logger = logging.getLogger(__name__)

_current_trace: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "analyze_trace", default=None
)

F = TypeVar("F", bound=Callable[..., Any])


def start_trace() -> list[dict[str, Any]]:
    """Bind a fresh trace list to the current context and return it."""
    entries: list[dict[str, Any]] = []
    _current_trace.set(entries)
    return entries


def get_trace() -> list[dict[str, Any]]:
    """Return the current trace list, or an empty list if none is active."""
    entries = _current_trace.get()
    return entries if entries is not None else []


def clear_trace() -> None:
    """Detach the current trace list — useful for test isolation."""
    _current_trace.set(None)


def record(tool: str, duration_ms: float, status: str = "ok") -> None:
    """Append a single trace entry if a trace is active; otherwise a no-op."""
    entries = _current_trace.get()
    if entries is None:
        return
    entries.append({"tool": tool, "duration_ms": round(duration_ms, 2), "status": status})


def traced(name: str) -> Callable[[F], F]:
    """Decorator: time the wrapped sync function and append a trace entry.

    Errors still propagate after the ``status="error"`` entry is recorded so
    the agent's existing error handling is unchanged.
    """

    def _wrap(func: F) -> F:
        @wraps(func)
        def _inner(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            status = "ok"
            try:
                return func(*args, **kwargs)
            except Exception:
                status = "error"
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                record(name, elapsed_ms, status)

        return _inner  # type: ignore[return-value]

    return _wrap
