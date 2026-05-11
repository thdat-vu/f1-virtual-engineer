"""Tests for /telemetry persistence + GET /telemetry/history (issue #94).

Mirrors `test_history_api.py`: dependency_overrides flip user identity per test
so we don't need a real Supabase JWT secret, and the persistence helpers are
patched on the `app.main` module so no test reaches PostgREST.
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


_VALID_USER_ID = "22222222-2222-2222-2222-222222222222"


def _telemetry_request_body() -> dict:
    return {
        "year": 2023,
        "event": "Japanese Grand Prix",
        "session_type": "R",
        "driver": "HAM",
        "lap_number": 25,
    }


def _telemetry_success_fixture() -> dict:
    """Minimal payload matching TelemetrySummary that satisfies Pydantic."""
    channel = {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": ""}
    return {
        "driver": "HAM",
        "year": 2023,
        "event": "Japanese Grand Prix",
        "session_type": "R",
        "sample_points": 100,
        "speed": channel,
        "gear": channel,
        "rpm": channel,
        "throttle": channel,
        "brake": channel,
        "fallback": False,
        "fallback_reason": None,
        "lap_number": 25,
        "lap_duration_s": 90.5,
        "sector_boundaries_s": [30.0, 60.0, 90.5],
    }


def _telemetry_fallback_fixture() -> dict:
    fixture = _telemetry_success_fixture()
    fixture["fallback"] = True
    fixture["fallback_reason"] = "Session unavailable in cache."
    return fixture


def _drain_tasks() -> None:
    """Same intent as in test_history_api: best-effort drain to silence
    "coroutine was never awaited" RuntimeWarnings on patched AsyncMocks."""
    import gc

    gc.collect()


class TelemetryPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_optional_user_id, None)
        app.dependency_overrides.pop(get_required_user_id, None)

    @patch("app.main.insert_telemetry_history", new_callable=AsyncMock)
    @patch("app.main.get_session_telemetry_summary")
    def test_telemetry_signed_in_writes_history(self, mock_summary, mock_insert):
        mock_summary.return_value = _telemetry_success_fixture()
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID

        response = self.client.post(
            "/telemetry",
            json=_telemetry_request_body(),
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        _drain_tasks()

        mock_insert.assert_called_once()
        kwargs = mock_insert.call_args.kwargs
        self.assertEqual(kwargs["user_id"], _VALID_USER_ID)
        self.assertEqual(kwargs["year"], 2023)
        self.assertEqual(kwargs["event"], "Japanese Grand Prix")
        self.assertEqual(kwargs["session_type"], "R")
        self.assertEqual(kwargs["driver"], "HAM")
        self.assertEqual(kwargs["lap_number"], 25)

    @patch("app.main.insert_telemetry_history", new_callable=AsyncMock)
    @patch("app.main.get_session_telemetry_summary")
    def test_telemetry_anonymous_skips_write(self, mock_summary, mock_insert):
        mock_summary.return_value = _telemetry_success_fixture()
        app.dependency_overrides[get_optional_user_id] = lambda: None

        response = self.client.post("/telemetry", json=_telemetry_request_body())
        self.assertEqual(response.status_code, 200)
        _drain_tasks()
        mock_insert.assert_not_called()

    @patch("app.main.insert_telemetry_history", new_callable=AsyncMock)
    @patch("app.main.get_session_telemetry_summary")
    def test_telemetry_invalid_jwt_treated_as_anonymous(self, mock_summary, mock_insert):
        mock_summary.return_value = _telemetry_success_fixture()
        app.dependency_overrides[get_optional_user_id] = lambda: None  # fail-closed

        response = self.client.post(
            "/telemetry",
            json=_telemetry_request_body(),
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        self.assertEqual(response.status_code, 200)
        _drain_tasks()
        mock_insert.assert_not_called()

    @patch("app.main.insert_telemetry_history", new_callable=AsyncMock)
    @patch("app.main.get_session_telemetry_summary")
    def test_telemetry_fallback_skips_persistence(self, mock_summary, mock_insert):
        mock_summary.return_value = _telemetry_fallback_fixture()
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID

        response = self.client.post(
            "/telemetry",
            json=_telemetry_request_body(),
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "TELEMETRY_UNAVAILABLE")
        _drain_tasks()
        mock_insert.assert_not_called()

    @patch("app.main.insert_telemetry_history", new_callable=AsyncMock)
    @patch("app.main.get_session_telemetry_summary")
    def test_telemetry_persistence_failure_does_not_break_response(self, mock_summary, mock_insert):
        mock_summary.return_value = _telemetry_success_fixture()
        mock_insert.side_effect = RuntimeError("postgrest down")
        app.dependency_overrides[get_optional_user_id] = lambda: _VALID_USER_ID

        response = self.client.post(
            "/telemetry",
            json=_telemetry_request_body(),
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        _drain_tasks()


class TelemetryHistoryEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_required_user_id, None)

    def test_history_returns_401_without_token(self):
        response = self.client.get("/telemetry/history")
        self.assertEqual(response.status_code, 401)

    def test_history_returns_401_with_invalid_token(self):
        def _raise_unauthorized():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
            )

        app.dependency_overrides[get_required_user_id] = _raise_unauthorized
        response = self.client.get(
            "/telemetry/history",
            headers={"Authorization": "Bearer not-real"},
        )
        self.assertEqual(response.status_code, 401)

    @patch("app.main.list_telemetry_history", new_callable=AsyncMock)
    def test_history_returns_user_rows_when_signed_in(self, mock_list):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        row = {
            "id": str(uuid4()),
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "driver": "HAM",
            "lap_number": 25,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_list.return_value = [row]
        response = self.client.get(
            "/telemetry/history",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["driver"], "HAM")
        self.assertEqual(payload["items"][0]["year"], 2023)
        mock_list.assert_called_once_with(user_id=_VALID_USER_ID, limit=20)

    @patch("app.main.list_telemetry_history", new_callable=AsyncMock)
    def test_history_forwards_limit_query_param(self, mock_list):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        mock_list.return_value = []
        response = self.client.get(
            "/telemetry/history?limit=7",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 200)
        mock_list.assert_called_once_with(user_id=_VALID_USER_ID, limit=7)

    def test_history_query_param_validation(self):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        too_low = self.client.get(
            "/telemetry/history?limit=0",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(too_low.status_code, 422)
        too_high = self.client.get(
            "/telemetry/history?limit=51",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(too_high.status_code, 422)

    @patch("app.main.list_telemetry_history", new_callable=AsyncMock)
    def test_history_returns_503_on_persistence_error(self, mock_list):
        app.dependency_overrides[get_required_user_id] = lambda: _VALID_USER_ID
        mock_list.side_effect = RuntimeError("postgrest down")
        response = self.client.get(
            "/telemetry/history",
            headers={"Authorization": "Bearer fake.jwt.token"},
        )
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["code"], "history_unavailable")

    def test_openapi_exposes_telemetry_history_endpoint(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("/telemetry/history", payload["paths"])
        history_get = payload["paths"]["/telemetry/history"]["get"]
        self.assertEqual(history_get["tags"], ["telemetry"])
        self.assertIn("TelemetryHistoryResponse", payload["components"]["schemas"])


if __name__ == "__main__":
    unittest.main()
