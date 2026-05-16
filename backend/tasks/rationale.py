"""Async LLM rationale back-fill task (#139 PR3).

Sync flow today:
  /analyze -> generate_rationale() (LLM round-trip) -> response

Async flow with ``RATIONALE_ASYNC=true``:
  /analyze -> insert_analyze_history(rationale_source='template') -> queue
              backfill_rationale.delay(row_id, user_id, llm_context)
            -> response with rationale_source='template' + rationale_job_id
  worker  -> generate_rationale() -> update_analyze_history_rationale(...)
            -> row flips to rationale_source='llm', rationale_text populated

Idempotency is enforced at the persistence layer: the update filters on
``rationale_source=eq.template``, so a re-delivered task on a row that's
already ``llm`` becomes a no-op. This task itself just calls into that
helper.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tasks import TaskWithDLQ, app
from tasks.exceptions import PermanentError, TransientError


logger = logging.getLogger("tasks.rationale")


def _run_async(coro: Any) -> Any:
    """Run a coroutine to completion from sync Celery task code.

    Workers run sync; the persistence helpers are async (httpx). Each
    call gets its own loop so we don't share an event loop across
    tasks (Celery's prefork model would make that fragile).
    """

    return asyncio.run(coro)


@app.task(
    name="tasks.rationale.backfill_rationale",
    bind=True,
    base=TaskWithDLQ,
    autoretry_for=(TransientError,),
    max_retries=3,
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
)
def backfill_rationale(
    self,
    row_id: str,
    user_id: str,
    llm_context: dict[str, Any],
) -> dict[str, Any]:
    """Generate the LLM rationale and patch it onto the history row.

    Returns ``{"updated": bool, "row_id": str}``. ``updated`` is False
    when the row was already at ``rationale_source='llm'`` (idempotent
    skip — re-deliveries are safe).

    Failure modes:
    - ``generate_rationale`` returns ``None`` -> ``TransientError``
      (autoretry; covers Gemini quota / network blips).
    - PostgREST is unconfigured or returns no row updated -> we treat
      it as a successful no-op rather than retry. The DLQ is reserved
      for cases the operator should look at.
    - Anything truly unexpected (TypeError on context, etc) -> falls
      through as a bare ``Exception`` which ``TaskWithDLQ`` treats as
      permanent and routes to the DLQ.
    """

    # Local imports keep this module importable when llm/persistence are
    # half-configured (e.g. unit tests that skip the real Gemini path).
    from core.llm import generate_rationale
    from core.persistence import update_analyze_history_rationale

    if not row_id or not user_id:
        # Bad enqueue -> DLQ on first try; not retry-able.
        raise PermanentError(
            f"backfill_rationale received empty identifiers row_id={row_id!r} user_id={user_id!r}"
        )

    text = generate_rationale(llm_context)
    if not text:
        # ``generate_rationale`` already swallows transport errors and
        # returns None when the LLM path declined to produce output.
        # Treat that as transient — Gemini outages and quota resets are
        # the most common cause and they recover on retry. After 3
        # retries it lands in the DLQ.
        raise TransientError("generate_rationale returned no text")

    updated = _run_async(
        update_analyze_history_rationale(
            user_id=user_id,
            row_id=row_id,
            rationale_text=text,
        )
    )
    return {"updated": bool(updated), "row_id": row_id}


__all__ = ["backfill_rationale"]
