"""Tests for /analyze persistence + GET /analyze/history (issue #93).

The strategy mirrors `test_analyze_api.py` and `test_radio_interpreter.py`:
patch `analyze_query` and the persistence helpers so no test reaches Supabase
or Gemini, and override the JWT-based FastAPI dependencies via
``app.dependency_overrides`` so we can flip user identity per test without
a real Supabase JWT secret.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from core.auth import get_optional_user_id, get_required_user_id
from tests._helpers import reset_rate_limiter


_VALID_USER_ID = "11111111-1111-1111-1111-111111111111"
_AGENT_RESPONSE_FIXTURE = {
    "intent": {
        "driver": "HAM",
        "year": 2023,
        "event": "Japanese Grand Prix",
        "session_type": "R",
        "intent_type": "telemetry",
    },
    "telemetry_data": {"fallback": False},
    "strategy_data": None,
    "response_text": "HAM telemetry summary.",
    "rationale_source": "template",
    "error": None,
    "memory": {"history_size": 1, "retention_cap": 10, "last_driver": "HAM"},
    "execution": {
        "termination_reason": "completed",
        "step_limit": 6,
        "duration_ms": 10.0,
        "duration_limit_seconds": 5.0,
    },
    "retry": {"count": 0, "max_retries": 2, "retryable_exhausted": False, "retry_backoff_seconds": 0.1},
}


def _analyze_request_body() -> dict:
    return {
        "query": "show ham telemetry",
        "driver": "HAM",
        "session_info": {"event": "Japanese Grand Prix", "year": 2023, "session_type": "R"},
    }


def _drain_tasks() -> None:
    """Best-effort drain of fire-and-forget tasks scheduled by the handler.

    TestClient runs each request on a short-lived event loop that closes
    when the response returns, so any ``asyncio.create_task`` scheduled
    inside the handler is recorded (the AsyncMock target is invoked
    synchronously) but its coroutine body may not execute. That's fine
    for `assert_called_once` / `assert_not_called` checks — call
    recording happens at coroutine *creation* time. We still call this
    helper to flush any leftover pending callbacks and silence
    "coroutine was never awaited" RuntimeWarnings in the failure-case
    test where insert raises.
    """
    import gc

    gc.collect()


class AnalyzePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_optional_user_id, None)
        app.dependency_overrides.pop(get_required_user_id, None)

    @patch("app.main.insert_analyze_history", new_callable=AsyncMock)
    @patch("app.main.analyze_query")
    def test_analyze_signed_in_writes_history(self, mock_analyze, mock_insert):
        mock_analyze.return_value = _AGENT_RESPONSE_FIXTURE
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID

        response = self.client.post(
            "/analyze",
            json=_analyze_request_body(),
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        _drain_tasks()

        mock_insert.assert_called_once()
        kwargs = mock_insert.call_args.kwargs
        self.assertEqual(kwargs["user_id"], _VALID_USER_ID)
        self.assertEqual(kwargs["query"], "show ham telemetry")
        self.assertEqual(kwargs["driver"], "HAM")
        self.assertEqual(kwargs["event"], "Japanese Grand Prix")
        self.assertEqual(kwargs["year"], 2023)
        self.assertEqual(kwargs["session_type"], "R")
        self.assertEqual(kwargs["agent_response"], "HAM telemetry summary.")
        self.assertEqual(kwargs["rationale_source"], "template")
        self.assertEqual(kwargs["intent_type"], "telemetry")

    @patch("app.main.insert_analyze_history", new_callable=AsyncMock)
    @patch("app.main.analyze_query")
    def test_analyze_anonymous_skips_write(self, mock_analyze, mock_insert):
        mock_analyze.return_value = _AGENT_RESPONSE_FIXTURE
        app.dependency_overrides[get_optional_user_id] = lambda: None

        response = self.client.post("/analyze", json=_analyze_request_body())
        self.assertEqual(response.status_code, 200)
        _drain_tasks()
        mock_insert.assert_not_called()

    @patch("app.main.insert_analyze_history", new_callable=AsyncMock)
    @patch("app.main.analyze_query")
    def test_analyze_invalid_jwt_treated_as_anonymous(self, mock_analyze, mock_insert):
        # get_optional_user_id is fail-closed: invalid token → returns None.
        mock_analyze.return_value = _AGENT_RESPONSE_FIXTURE
        app.dependency_overrides[get_optional_user_id] = lambda: None

        response = self.client.post(
            "/analyze",
            json=_analyze_request_body(),
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        self.assertEqual(response.status_code, 200)
        _drain_tasks()
        mock_insert.assert_not_called()

    @patch("app.main.insert_analyze_history", new_callable=AsyncMock)
    @patch("app.main.analyze_query")
    def test_analyze_persistence_failure_does_not_break_response(self, mock_analyze, mock_insert):
        mock_analyze.return_value = _AGENT_RESPONSE_FIXTURE
        mock_insert.side_effect = RuntimeError("postgrest down")
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID

        response = self.client.post(
            "/analyze",
            json=_analyze_request_body(),
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        _drain_tasks()

    @patch("app.main.insert_analyze_history", new_callable=AsyncMock)
    @patch("app.main.analyze_query")
    def test_analyze_with_error_skips_persistence(self, mock_analyze, mock_insert):
        errored = dict(_AGENT_RESPONSE_FIXTURE)
        errored["error"] = "Telemetry unavailable for the requested driver."
        mock_analyze.return_value = errored
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID

        response = self.client.post(
            "/analyze",
            json=_analyze_request_body(),
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        _drain_tasks()
        mock_insert.assert_not_called()


class HistoryEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_required_user_id, None)

    def test_history_returns_401_without_token(self):
        # Real dep runs because we don't override; missing Authorization → 401.
        response = self.client.get("/analyze/history")
        self.assertEqual(response.status_code, 401)

    def test_history_returns_401_with_invalid_token(self):
        def _raise_unauthorized():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
            )

        app.dependency_overrides[get_required_user_id] = _raise_unauthorized
        response = self.client.get(
            "/analyze/history",
            headers={"Authorization": "Bearer not-real"},
        )
        self.assertEqual(response.status_code, 401)

    @patch("app.main.list_analyze_history", new_callable=AsyncMock)
    def test_history_returns_user_rows_when_signed_in(self, mock_list):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        row = {
            "id": str(uuid4()),
            "query": "show ham telemetry",
            "driver": "HAM",
            "event": "Japanese Grand Prix",
            "year": 2023,
            "session_type": "R",
            "intent_type": "telemetry",
            "rationale_source": "template",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_list.return_value = [row]
        response = self.client.get(
            "/analyze/history",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["query"], "show ham telemetry")
        self.assertEqual(payload["items"][0]["driver"], "HAM")
        mock_list.assert_called_once_with(user_id=_VALID_USER_ID, limit=20)

    @patch("app.main.list_analyze_history", new_callable=AsyncMock)
    def test_history_forwards_limit_query_param(self, mock_list):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        mock_list.return_value = []
        response = self.client.get(
            "/analyze/history?limit=5",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        mock_list.assert_called_once_with(user_id=_VALID_USER_ID, limit=5)

    def test_history_query_param_validation(self):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        too_low = self.client.get(
            "/analyze/history?limit=0",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(too_low.status_code, 422)
        too_high = self.client.get(
            "/analyze/history?limit=51",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(too_high.status_code, 422)

    @patch("app.main.list_analyze_history", new_callable=AsyncMock)
    def test_history_returns_503_on_persistence_error(self, mock_list):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        mock_list.side_effect = RuntimeError("postgrest down")
        response = self.client.get(
            "/analyze/history",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["code"], "history_unavailable")

    def test_openapi_exposes_history_endpoint(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("/analyze/history", payload["paths"])
        history_get = payload["paths"]["/analyze/history"]["get"]
        self.assertEqual(history_get["tags"], ["analysis"])
        self.assertIn("AnalyzeHistoryResponse", payload["components"]["schemas"])


class AuthHelperUnitTests(unittest.TestCase):
    """Light unit tests for core/auth helpers that don't touch FastAPI."""

    def test_verify_supabase_jwt_returns_none_when_secret_missing(self):
        from core.auth import verify_supabase_jwt
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("SUPABASE_JWT_SECRET", None)
            self.assertIsNone(verify_supabase_jwt("any.token.here"))

    def test_verify_supabase_jwt_returns_none_for_garbage_token(self):
        from core.auth import verify_supabase_jwt
        import os
        os.environ["SUPABASE_JWT_SECRET"] = "test-secret"
        try:
            self.assertIsNone(verify_supabase_jwt("not.a.real.jwt"))
        finally:
            os.environ.pop("SUPABASE_JWT_SECRET", None)

    def test_verify_supabase_jwt_round_trip(self):
        import os
        import jwt as pyjwt
        from core.auth import verify_supabase_jwt

        secret = "test-secret-abc-padded-to-32-bytes!!"
        token = pyjwt.encode(
            {"sub": "user-123", "aud": "authenticated"},
            secret,
            algorithm="HS256",
        )
        os.environ["SUPABASE_JWT_SECRET"] = secret
        try:
            claims = verify_supabase_jwt(token)
            self.assertIsNotNone(claims)
            self.assertEqual(claims["sub"], "user-123")
        finally:
            os.environ.pop("SUPABASE_JWT_SECRET", None)


if __name__ == "__main__":
    unittest.main()
