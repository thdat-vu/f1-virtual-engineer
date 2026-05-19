"""Tests for the Idempotency-Key dedupe layer on POST /analyze (#161)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from core import idempotency
from core.auth import get_optional_user_id
from tests._helpers import reset_rate_limiter


_ANALYZE_FIXTURE = {
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


def _request_body() -> dict:
    return {
        "query": "show ham telemetry",
        "driver": "HAM",
        "session_info": {"event": "Japanese Grand Prix", "year": 2023, "session_type": "R"},
    }


class IdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limiter()
        self.client = TestClient(app)
        # Anonymous so we don't drag the persistence path into these tests —
        # the dedupe layer wraps the entire handler so the auth state doesn't
        # change the contract we care about here.
        app.dependency_overrides[get_optional_user_id] = lambda: None

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_optional_user_id, None)

    @patch("app.main.analyze_query")
    @patch("core.idempotency._get_client_or_none", create=True)  # noqa: PT008 — module-level redis stub
    def test_no_header_runs_normally_and_skips_cache(self, _stub, mock_analyze):
        # Without an Idempotency-Key header, the handler must not touch the
        # idempotency module at all (no lookup, no reserve, no commit).
        mock_analyze.return_value = _ANALYZE_FIXTURE

        with patch.object(idempotency, "lookup") as mock_lookup, \
             patch.object(idempotency, "reserve") as mock_reserve, \
             patch.object(idempotency, "commit") as mock_commit:
            response = self.client.post("/analyze", json=_request_body())
            self.assertEqual(response.status_code, 200)
            mock_lookup.assert_not_called()
            mock_reserve.assert_not_called()
            mock_commit.assert_not_called()

    @patch("app.main.analyze_query")
    def test_cache_miss_runs_agent_and_commits(self, mock_analyze):
        mock_analyze.return_value = _ANALYZE_FIXTURE
        key = str(uuid4())

        with patch.object(idempotency, "lookup", return_value=None) as mock_lookup, \
             patch.object(idempotency, "reserve", return_value=True) as mock_reserve, \
             patch.object(idempotency, "commit") as mock_commit:
            response = self.client.post(
                "/analyze",
                json=_request_body(),
                headers={"Idempotency-Key": key},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "success")

            mock_lookup.assert_called_once_with(key)
            mock_reserve.assert_called_once_with(key)
            mock_commit.assert_called_once()
            committed_key, committed_payload = mock_commit.call_args.args
            self.assertEqual(committed_key, key)
            self.assertEqual(committed_payload["status"], "success")
            mock_analyze.assert_called_once()

    @patch("app.main.analyze_query")
    def test_cache_hit_done_short_circuits_agent(self, mock_analyze):
        # A cached "done" entry must return immediately without invoking
        # the agent or rewriting the cache.
        cached_payload = {
            "status": "success",
            "agent_response": "cached HAM summary",
            "query": "show ham telemetry",
            "intent": {"intent_type": "telemetry"},
            "telemetry_data": {"fallback": False},
            "strategy_data": None,
            "rationale_source": "template",
            "rationale_job_id": None,
            "analyze_history_id": None,
            "error": None,
            "memory": None,
            "execution": None,
            "retry": None,
            "citations": [],
        }
        key = str(uuid4())

        with patch.object(
            idempotency,
            "lookup",
            return_value=(idempotency.STATUS_DONE, cached_payload),
        ), patch.object(idempotency, "reserve") as mock_reserve, \
             patch.object(idempotency, "commit") as mock_commit:
            response = self.client.post(
                "/analyze",
                json=_request_body(),
                headers={"Idempotency-Key": key},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_response"], "cached HAM summary")
        mock_analyze.assert_not_called()
        mock_reserve.assert_not_called()
        mock_commit.assert_not_called()

    @patch("app.main.analyze_query")
    def test_cache_hit_pending_returns_409(self, mock_analyze):
        # Concurrent request with the same key in flight → 409 + Retry-After.
        key = str(uuid4())
        with patch.object(
            idempotency,
            "lookup",
            return_value=(idempotency.STATUS_PENDING, None),
        ), patch.object(idempotency, "reserve") as mock_reserve:
            response = self.client.post(
                "/analyze",
                json=_request_body(),
                headers={"Idempotency-Key": key},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.headers.get("Retry-After"), "2")
        mock_analyze.assert_not_called()
        mock_reserve.assert_not_called()

    @patch("app.main.analyze_query")
    def test_reserve_loses_race_returns_409(self, mock_analyze):
        # Two requests slip past lookup() before either reserves; the loser
        # of SETNX must surface 409 instead of running the agent.
        key = str(uuid4())
        with patch.object(idempotency, "lookup", return_value=None), \
             patch.object(idempotency, "reserve", return_value=False), \
             patch.object(idempotency, "commit") as mock_commit:
            response = self.client.post(
                "/analyze",
                json=_request_body(),
                headers={"Idempotency-Key": key},
            )
        self.assertEqual(response.status_code, 409)
        mock_analyze.assert_not_called()
        mock_commit.assert_not_called()


class IdempotencyHelperTests(unittest.TestCase):
    """Direct unit tests for the helper module — no FastAPI in the loop."""

    def test_lookup_returns_none_when_redis_disabled(self):
        with patch("core.idempotency.redis_cache._get_client", return_value=None):
            self.assertIsNone(idempotency.lookup("any-key"))

    def test_lookup_decodes_done_entry(self):
        client = MagicMock()
        client.get.return_value = json.dumps(
            {"status": "done", "payload": {"agent_response": "hello"}}
        )
        with patch("core.idempotency.redis_cache._get_client", return_value=client):
            status, payload = idempotency.lookup("k")
        self.assertEqual(status, "done")
        self.assertEqual(payload, {"agent_response": "hello"})

    def test_lookup_swallows_redis_errors(self):
        client = MagicMock()
        client.get.side_effect = RuntimeError("redis down")
        with patch("core.idempotency.redis_cache._get_client", return_value=client):
            self.assertIsNone(idempotency.lookup("k"))

    def test_reserve_returns_true_when_setnx_succeeds(self):
        client = MagicMock()
        client.set.return_value = True
        with patch("core.idempotency.redis_cache._get_client", return_value=client):
            self.assertTrue(idempotency.reserve("k"))
        # SETNX must be invoked — without nx=True two concurrent reservations
        # both pass and we lose the dedupe guarantee.
        _args, kwargs = client.set.call_args
        self.assertTrue(kwargs.get("nx"))
        self.assertEqual(kwargs.get("ex"), idempotency.TTL_SECONDS)

    def test_reserve_returns_false_when_key_exists(self):
        client = MagicMock()
        client.set.return_value = None
        with patch("core.idempotency.redis_cache._get_client", return_value=client):
            self.assertFalse(idempotency.reserve("k"))

    def test_release_deletes_key(self):
        client = MagicMock()
        with patch("core.idempotency.redis_cache._get_client", return_value=client):
            idempotency.release("k")
        client.delete.assert_called_once()


if __name__ == "__main__":
    unittest.main()
