"""Tests for /saved-queries CRUD (issue #104).

Mirrors test_history_api.py: patch persistence helpers and override JWT deps
via app.dependency_overrides.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from core.auth import get_required_user_id
from tests._helpers import reset_rate_limiter


_USER_A = "11111111-1111-1111-1111-11111111aaaa"

_ANALYZE_PAYLOAD = {
    "query": "how fast was VER at Monza?",
    "driver": "VER",
    "session_info": {"event": "Italian Grand Prix", "year": 2024, "session_type": "R"},
}

_SAVED_ROW_FIXTURE = {
    "id": str(uuid4()),
    "kind": "analyze",
    "payload": _ANALYZE_PAYLOAD,
    "label": None,
    "created_at": datetime.now(timezone.utc).isoformat(),
}


class SavedQueriesAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        app.dependency_overrides = {}

    def tearDown(self) -> None:
        app.dependency_overrides = {}

    def test_post_401_without_token(self):
        with TestClient(app) as client:
            resp = client.post("/saved-queries", json={"kind": "analyze", "payload": {}})
        self.assertEqual(resp.status_code, 401)

    def test_get_401_without_token(self):
        with TestClient(app) as client:
            resp = client.get("/saved-queries")
        self.assertEqual(resp.status_code, 401)

    def test_delete_401_without_token(self):
        with TestClient(app) as client:
            resp = client.delete(f"/saved-queries/{uuid4()}")
        self.assertEqual(resp.status_code, 401)


class SavedQueriesRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        app.dependency_overrides = {get_required_user_id: lambda: _USER_A}

    def tearDown(self) -> None:
        app.dependency_overrides = {}

    def test_post_creates_row(self):
        with patch(
            "app.main.insert_saved_query",
            new_callable=AsyncMock,
            return_value=_SAVED_ROW_FIXTURE,
        ) as mock_insert:
            with TestClient(app) as client:
                resp = client.post(
                    "/saved-queries",
                    json={"kind": "analyze", "payload": _ANALYZE_PAYLOAD},
                )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["kind"], "analyze")
        self.assertEqual(body["payload"], _ANALYZE_PAYLOAD)
        kwargs = mock_insert.call_args.kwargs
        self.assertEqual(kwargs["user_id"], _USER_A)
        self.assertEqual(kwargs["kind"], "analyze")

    def test_post_rejects_bad_kind(self):
        with TestClient(app) as client:
            resp = client.post(
                "/saved-queries",
                json={"kind": "radio", "payload": {}},
            )
        self.assertEqual(resp.status_code, 422)

    def test_post_rejects_long_label(self):
        with TestClient(app) as client:
            resp = client.post(
                "/saved-queries",
                json={"kind": "analyze", "payload": {}, "label": "x" * 500},
            )
        self.assertEqual(resp.status_code, 422)

    def test_get_returns_items(self):
        with patch(
            "app.main.list_saved_queries",
            new_callable=AsyncMock,
            return_value=[_SAVED_ROW_FIXTURE],
        ):
            with TestClient(app) as client:
                resp = client.get("/saved-queries")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["items"]), 1)

    def test_get_limit_validation(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/saved-queries?limit=0").status_code, 422)
            self.assertEqual(client.get("/saved-queries?limit=101").status_code, 422)

    def test_delete_success_returns_204(self):
        with patch(
            "app.main.delete_saved_query",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_delete:
            with TestClient(app) as client:
                resp = client.delete(f"/saved-queries/{uuid4()}")
        self.assertEqual(resp.status_code, 204)
        mock_delete.assert_called_once()

    def test_delete_other_user_row_returns_404(self):
        """Cross-user delete must 404, not 403 — avoids leaking id existence."""
        with patch(
            "app.main.delete_saved_query",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with TestClient(app) as client:
                resp = client.delete(f"/saved-queries/{uuid4()}")
        self.assertEqual(resp.status_code, 404)

    def test_post_503_on_db_error(self):
        async def _raise(*args, **kwargs):
            raise RuntimeError("db down")
        with patch("app.main.insert_saved_query", side_effect=_raise):
            with TestClient(app) as client:
                resp = client.post(
                    "/saved-queries",
                    json={"kind": "analyze", "payload": {}},
                )
        self.assertEqual(resp.status_code, 503)

    def test_delete_503_on_db_error(self):
        async def _raise(*args, **kwargs):
            raise RuntimeError("db down")
        with patch("app.main.delete_saved_query", side_effect=_raise):
            with TestClient(app) as client:
                resp = client.delete(f"/saved-queries/{uuid4()}")
        self.assertEqual(resp.status_code, 503)

    def test_openapi_routes_registered(self):
        with TestClient(app) as client:
            schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        self.assertIn("/saved-queries", paths)
        self.assertIn("post", paths["/saved-queries"])
        self.assertIn("get", paths["/saved-queries"])
        self.assertIn("/saved-queries/{query_id}", paths)
        self.assertIn("delete", paths["/saved-queries/{query_id}"])


class SavedQueriesInvalidTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        app.dependency_overrides = {}

    def tearDown(self) -> None:
        app.dependency_overrides = {}

    def test_get_401_with_invalid_token_dep(self):
        def _raise():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid.")
        app.dependency_overrides[get_required_user_id] = _raise
        with TestClient(app) as client:
            resp = client.get("/saved-queries")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
