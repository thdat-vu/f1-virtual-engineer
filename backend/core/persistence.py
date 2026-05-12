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
) -> None:
    """Insert one row into ``analyze_history``. Fail-closed: never raises."""
    try:
        client = await _get_client()
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("Failed to initialise persistence client", exc_info=True)
        return
    if client is None:
        _logger.debug("Supabase persistence not configured; skipping history insert")
        return
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
        response = await client.post(
            "/analyze_history",
            json=payload,
            headers={"Prefer": "return=minimal"},
        )
        if response.status_code >= 400:
            _logger.warning(
                "PostgREST insert failed (status=%s body=%r)",
                response.status_code,
                response.text[:300],
            )
    except Exception:  # noqa: BLE001 — fail-closed
        _logger.warning("PostgREST insert raised; swallowing", exc_info=True)


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
