"""Tests for /radio/analyze persistence + GET /radio/history (issue #95).

Mirrors test_history_api.py: patch interpret_radio and persistence helpers
so no test reaches Supabase or Gemini. Override JWT deps via
app.dependency_overrides to flip user identity per test.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from core.auth import get_optional_user_id, get_required_user_id
from tests._helpers import reset_rate_limiter


_VALID_USER_ID = "22222222-2222-2222-2222-222222222222"

_RADIO_RESULT_FIXTURE = {
    "classification": "tyre_issue",
    "severity": "high",
    "trigger_phrase": "blistering on the rears",
    "fallback": False,
    "fallback_reason": None,
}

_RADIO_HISTORY_FIXTURE = [
    {
        "id": str(uuid4()),
        "transcript": "Box box, blistering on the rears",
        "driver": "VER",
        "classification": "tyre_issue",
        "severity": "high",
        "trigger_phrase": "blistering on the rears",
        "fallback": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
]


def _radio_request_body(driver: str = "VER") -> dict:
    return {"transcript": "Box box, blistering on the rears", "driver": driver}


def _drain_tasks() -> None:
    loop = asyncio.new_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    loop.close()


class RadioAnalyzePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        app.dependency_overrides = {}

    def tearDown(self) -> None:
        app.dependency_overrides = {}

    def test_signed_in_writes_radio_history(self):
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID
        with (
            patch("app.main.interpret_radio", return_value=_RADIO_RESULT_FIXTURE),
            patch("app.main.insert_radio_history", new_callable=AsyncMock) as mock_insert,
        ):
            with TestClient(app) as client:
                resp = client.post("/radio/analyze", json=_radio_request_body())
            _drain_tasks()
        self.assertEqual(resp.status_code, 200)
        mock_insert.assert_called_once()
        call_kwargs = mock_insert.call_args.kwargs
        self.assertEqual(call_kwargs["user_id"], _VALID_USER_ID)
        self.assertEqual(call_kwargs["classification"], "tyre_issue")
        self.assertEqual(call_kwargs["severity"], "high")
        self.assertFalse(call_kwargs["fallback"])

    def test_anonymous_skips_radio_history(self):
        app.dependency_overrides[get_optional_user_id] = lambda: None
        with (
            patch("app.main.interpret_radio", return_value=_RADIO_RESULT_FIXTURE),
            patch("app.main.insert_radio_history", new_callable=AsyncMock) as mock_insert,
        ):
            with TestClient(app) as client:
                resp = client.post("/radio/analyze", json=_radio_request_body())
            _drain_tasks()
        self.assertEqual(resp.status_code, 200)
        mock_insert.assert_not_called()

    def test_persistence_failure_does_not_break_response(self):
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID
        async def _raise(*args, **kwargs):
            raise RuntimeError("db down")
        with (
            patch("app.main.interpret_radio", return_value=_RADIO_RESULT_FIXTURE),
            patch("app.main.insert_radio_history", side_effect=_raise),
        ):
            with TestClient(app) as client:
                resp = client.post("/radio/analyze", json=_radio_request_body())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["classification"], "tyre_issue")

    def test_fallback_result_still_persisted(self):
        """Fallback classifications are still written — the user should see them in history."""
        fallback_result = {
            "classification": "none",
            "severity": "low",
            "trigger_phrase": "",
            "fallback": True,
            "fallback_reason": "LLM unavailable",
        }
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID
        with (
            patch("app.main.interpret_radio", return_value=fallback_result),
            patch("app.main.insert_radio_history", new_callable=AsyncMock) as mock_insert,
        ):
            with TestClient(app) as client:
                resp = client.post("/radio/analyze", json=_radio_request_body())
            _drain_tasks()
        self.assertEqual(resp.status_code, 200)
        mock_insert.assert_called_once()
        self.assertTrue(mock_insert.call_args.kwargs["fallback"])


class RadioHistoryEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        app.dependency_overrides = {}

    def tearDown(self) -> None:
        app.dependency_overrides = {}

    def test_history_returns_401_without_token(self):
        with TestClient(app) as client:
            resp = client.get("/radio/history")
        self.assertEqual(resp.status_code, 401)

    def test_history_returns_401_with_invalid_token(self):
        def _raise():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
        app.dependency_overrides[get_required_user_id] = _raise
        with TestClient(app) as client:
            resp = client.get("/radio/history")
        self.assertEqual(resp.status_code, 401)

    def test_history_returns_rows_when_signed_in(self):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        with patch(
            "app.main.list_radio_history",
            new_callable=AsyncMock,
            return_value=_RADIO_HISTORY_FIXTURE,
        ):
            with TestClient(app) as client:
                resp = client.get("/radio/history")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["classification"], "tyre_issue")

    def test_history_driver_filter_passed_through(self):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        with patch(
            "app.main.list_radio_history",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list:
            with TestClient(app) as client:
                resp = client.get("/radio/history?driver=VER")
        self.assertEqual(resp.status_code, 200)
        mock_list.assert_called_once()
        self.assertEqual(mock_list.call_args.kwargs["driver"], "VER")

    def test_history_limit_validation(self):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        with TestClient(app) as client:
            self.assertEqual(client.get("/radio/history?limit=0").status_code, 422)
            self.assertEqual(client.get("/radio/history?limit=51").status_code, 422)

    def test_history_503_on_db_error(self):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        async def _raise(*args, **kwargs):
            raise RuntimeError("db down")
        with patch("app.main.list_radio_history", side_effect=_raise):
            with TestClient(app) as client:
                resp = client.get("/radio/history")
        self.assertEqual(resp.status_code, 503)

    def test_openapi_radio_history_registered(self):
        with TestClient(app) as client:
            schema = client.get("/openapi.json").json()
        self.assertIn("/radio/history", schema["paths"])


if __name__ == "__main__":
    unittest.main()
