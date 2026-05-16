"""PostgREST wrapper for Supabase-backed persistence of /analyze history.

Public surface:
- ``insert_analyze_history(...)`` — fire-and-forget write; logs + swallows on failure
  so persistence outages never break the /analyze response envelope.
- ``list_analyze_history(user_id, limit)`` — read for the history endpoint;
  raises on transport error so the caller can return 5xx.

Design notes:
- We talk to PostgREST directly (via httpx) instead of the supabase-py SDK to
  keep backend deps light and to avoid pulling in storage/realtime.
- Auth uses the **service-role** key, which bypasses RLS. The caller is
  responsible for passing only verified user ids (we trust the JWT ``sub``
  claim, never anything client-provided).
- Single-process MVP: a module-level lazy AsyncClient is reused.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx


_logger = logging.getLogger(__name__)
_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


def _get_supabase_url() -> str | None:
    return os.environ.get("SUPABASE_URL") or None


def _get_service_role_key() -> str | None:
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or None


async def _get_client() -> httpx.AsyncClient | None:
    global _client
    url = _get_supabase_url()
    key = _get_service_role_key()
    if not url or not key:
        return None
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is None:
            _client = httpx.AsyncClient(
                base_url=f"{url.rstrip('/')}/rest/v1",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(5.0),
            )
    return _client


async def _reset_client_for_tests() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def insert_analyze_history(
    *,
    user_id: str,
    query: str,
    driver: str | None,
    event: str | None,
    year: int | None,
    session_type: str | None,
    agent_response: str,
    rationale_source: str,
    intent_type: str | None,
) -> str | None:
    """Insert one row into ``analyze_history``. Fail-closed: never raises.

    Returns the new row's ``id`` on success so the async-rationale path
    (#139 PR3) can hand it to the worker for back-fill. Returns ``None``
    when persistence is unconfigured or the insert fails — fire-and-
    forget callers can keep ignoring the return value.
    """
    try:
        client = await _get_client()
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Failed to initialise persistence client", exc_info=True)
        return None
    if client is None:
        _logger.debug("Supabase persistence not configured; skipping history insert")
        return None
    payload = {
        "user_id": user_id,
        "query": query,
        "driver": driver,
        "event": event,
        "year": year,
        "session_type": session_type,
        "agent_response": agent_response,
        "rationale_source": rationale_source,
        "intent_type": intent_type,
    }
    try:
        # ``Prefer: return=representation`` makes PostgREST echo the inserted
        # row(s). We need it for the row id; the response body is small.
        response = await client.post(
            "/analyze_history",
            json=payload,
            headers={"Prefer": "return=representation"},
        )
        if response.status_code >= 400:
            _logger.warning(
                "PostgREST insert failed (status=%s body=%r)",
                response.status_code,
                response.text[:300],
            )
            return None
        body = response.json()
        if isinstance(body, list) and body and isinstance(body[0], dict):
            row_id = body[0].get("id")
            return str(row_id) if row_id is not None else None
        return None
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("PostgREST insert raised; swallowing", exc_info=True)
        return None


async def update_analyze_history_rationale(
    *,
    user_id: str,
    row_id: str,
    rationale_text: str,
) -> bool:
    """Back-fill ``rationale_text`` + flip ``rationale_source`` to ``"llm"``.

    Idempotent: filters on ``rationale_source=eq.template`` so a
    re-delivered Celery task can't double-write or clobber a freshly
    refreshed value. Returns ``True`` when a row was actually updated,
    ``False`` otherwise (already upgraded, missing, or persistence
    disabled).
    """
    try:
        client = await _get_client()
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Failed to initialise persistence client", exc_info=True)
        return False
    if client is None:
        return False
    try:
        response = await client.patch(
            "/analyze_history",
            params={
                "id": f"eq.{row_id}",
                "user_id": f"eq.{user_id}",
                "rationale_source": "eq.template",
            },
            json={
                "rationale_text": rationale_text,
                "rationale_source": "llm",
            },
            headers={"Prefer": "return=representation"},
        )
        if response.status_code >= 400:
            _logger.warning(
                "PostgREST update failed (status=%s body=%r)",
                response.status_code,
                response.text[:300],
            )
            return False
        body = response.json()
        # Empty list -> the WHERE didn't match (already upgraded or row
        # removed). Treating that as "not updated" is what we want for
        # idempotency.
        return isinstance(body, list) and len(body) > 0
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("PostgREST update raised; swallowing", exc_info=True)
        return False


async def list_analyze_history(*, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent rows for ``user_id`` ordered by created_at desc.

    Raises ``httpx.HTTPError`` on transport error so the caller can decide
    whether to surface 5xx — for the history endpoint we want failures to be
    visible rather than masked as empty.
    """
    client = await _get_client()
    if client is None:
        return []
    response = await client.get(
        "/analyze_history",
        params={
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "limit": str(limit),
            "select": (
                "id,query,driver,event,year,session_type,intent_type,"
                "rationale_source,created_at"
            ),
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    return payload


async def insert_telemetry_history(
    *,
    user_id: str,
    year: int,
    event: str,
    session_type: str,
    driver: str,
    lap_number: int | None,
) -> None:
    """Insert one row into ``telemetry_history``. Fail-closed: never raises."""
    try:
        client = await _get_client()
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Failed to initialise persistence client", exc_info=True)
        return
    if client is None:
        _logger.debug("Supabase persistence not configured; skipping telemetry history insert")
        return
    payload = {
        "user_id": user_id,
        "year": year,
        "event": event,
        "session_type": session_type,
        "driver": driver,
        "lap_number": lap_number,
    }
    try:
        response = await client.post(
            "/telemetry_history",
            json=payload,
            headers={"Prefer": "return=minimal"},
        )
        if response.status_code >= 400:
            _logger.warning(
                "PostgREST telemetry insert failed (status=%s body=%r)",
                response.status_code,
                response.text[:300],
            )
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("PostgREST telemetry insert raised; swallowing", exc_info=True)


async def list_telemetry_history(*, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent telemetry lookups for ``user_id`` (newest first).

    Raises ``httpx.HTTPError`` on transport error so the caller can return 5xx.
    """
    client = await _get_client()
    if client is None:
        return []
    response = await client.get(
        "/telemetry_history",
        params={
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "limit": str(limit),
            "select": "id,year,event,session_type,driver,lap_number,created_at",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    return payload


async def insert_radio_history(
    *,
    user_id: str,
    transcript: str,
    driver: str | None,
    classification: str,
    severity: str,
    trigger_phrase: str | None,
    fallback: bool,
) -> None:
    """Insert one row into ``radio_history``. Fail-closed: never raises."""
    try:
        client = await _get_client()
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Failed to initialise persistence client", exc_info=True)
        return
    if client is None:
        _logger.debug("Supabase persistence not configured; skipping radio history insert")
        return
    payload = {
        "user_id": user_id,
        "transcript": transcript,
        "driver": driver,
        "classification": classification,
        "severity": severity,
        "trigger_phrase": trigger_phrase,
        "fallback": fallback,
    }
    try:
        response = await client.post(
            "/radio_history",
            json=payload,
            headers={"Prefer": "return=minimal"},
        )
        if response.status_code >= 400:
            _logger.warning(
                "PostgREST radio insert failed (status=%s body=%r)",
                response.status_code,
                response.text[:300],
            )
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("PostgREST radio insert raised; swallowing", exc_info=True)


async def list_radio_history(
    *, user_id: str, limit: int = 20, driver: str | None = None
) -> list[dict[str, Any]]:
    """Return the most recent radio classifications for ``user_id`` (newest first).

    Optionally filtered by ``driver``. Raises ``httpx.HTTPError`` on transport error.
    """
    client = await _get_client()
    if client is None:
        return []
    params: dict[str, str] = {
        "user_id": f"eq.{user_id}",
        "order": "created_at.desc",
        "limit": str(limit),
        "select": "id,transcript,driver,classification,severity,trigger_phrase,fallback,created_at",
    }
    if driver:
        params["driver"] = f"eq.{driver}"
    response = await client.get("/radio_history", params=params)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    return payload


async def insert_saved_query(
    *,
    user_id: str,
    kind: str,
    payload: dict[str, Any],
    label: str | None,
) -> dict[str, Any] | None:
    """Insert one row into ``saved_queries`` and return it. Raises on transport error."""
    client = await _get_client()
    if client is None:
        return None
    body = {
        "user_id": user_id,
        "kind": kind,
        "payload": payload,
        "label": label,
    }
    response = await client.post(
        "/saved_queries",
        json=body,
        headers={"Prefer": "return=representation"},
    )
    response.raise_for_status()
    rows = response.json()
    if isinstance(rows, list) and rows:
        return rows[0]
    if isinstance(rows, dict):
        return rows
    return None


async def list_saved_queries(*, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return saved queries for ``user_id`` newest-first. Raises on transport error."""
    client = await _get_client()
    if client is None:
        return []
    response = await client.get(
        "/saved_queries",
        params={
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "limit": str(limit),
            "select": "id,kind,payload,label,created_at",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    return payload


async def delete_saved_query(*, user_id: str, query_id: str) -> bool:
    """Delete a saved query if it belongs to ``user_id``. Returns True when a row
    was deleted. Raises ``httpx.HTTPError`` on transport error so the caller can
    distinguish "not yours" (False) from "db down" (5xx)."""
    client = await _get_client()
    if client is None:
        return False
    response = await client.delete(
        "/saved_queries",
        params={
            "id": f"eq.{query_id}",
            "user_id": f"eq.{user_id}",
        },
        headers={"Prefer": "return=representation"},
    )
    response.raise_for_status()
    rows = response.json()
    if isinstance(rows, list):
        return len(rows) > 0
    return False
