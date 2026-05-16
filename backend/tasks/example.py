"""Smoke-test task for the Celery scaffold.

This exists so we can verify the worker is wired up end-to-end before
porting any real workload (the LLM rationale path lands in PR3 of #139).
Inside the worker container:

    python -c "from tasks.example import ping; print(ping.delay('hi').get(timeout=5))"

should print ``pong: hi``.
"""

from __future__ import annotations

from tasks import app


@app.task(name="tasks.example.ping")
def ping(text: str) -> str:
    return f"pong: {text}"
