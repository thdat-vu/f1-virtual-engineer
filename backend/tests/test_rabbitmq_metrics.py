"""Tests for the live worker metrics scraped from RabbitMQ (#139 PR6).

We don't reach a real broker; ``httpx.AsyncClient`` is patched so each
test pins a specific failure or success mode. The goal is to lock in the
fail-closed contract: any blip on the management API resolves to zeros
plus ``broker_reachable: false`` so ``/metrics`` itself never 5xxs.
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from core.rabbitmq_metrics import fetch_queue_stats, snapshot_worker_metrics


def _stub_response(status_code: int, payload: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if payload is None:
        response.json.side_effect = ValueError("no payload")
    else:
        response.json.return_value = payload
    return response


class FetchQueueStatsTests(unittest.IsolatedAsyncioTestCase):
    @patch.dict(
        "os.environ",
        {"RABBITMQ_PASSWORD": "x", "RABBITMQ_MANAGEMENT_URL": "http://broker:15672"},
    )
    async def test_returns_stats_on_200(self):
        client = MagicMock()
        client.get = AsyncMock(
            return_value=_stub_response(
                200,
                {
                    "messages_ready": 7,
                    "messages_unacknowledged": 3,
                    "messages": 10,
                },
            ),
        )
        stats = await fetch_queue_stats("apex.tasks", client=client)
        self.assertEqual(stats, {
            "messages_ready": 7,
            "messages_unacknowledged": 3,
            "messages": 10,
        })
        # The auth tuple must be derived from RABBITMQ_PASSWORD; otherwise
        # the management plugin returns 401 even on the healthy path.
        _args, kwargs = client.get.call_args
        self.assertEqual(kwargs["auth"], ("apex", "x"))

    async def test_no_credentials_returns_none(self):
        # No RABBITMQ_PASSWORD in env → bail out before making the HTTP call.
        with patch.dict("os.environ", {"RABBITMQ_PASSWORD": ""}, clear=False):
            stats = await fetch_queue_stats("apex.tasks")
        self.assertIsNone(stats)

    @patch.dict("os.environ", {"RABBITMQ_PASSWORD": "x"})
    async def test_404_returns_none(self):
        client = MagicMock()
        client.get = AsyncMock(return_value=_stub_response(404))
        stats = await fetch_queue_stats("apex.tasks.dead", client=client)
        self.assertIsNone(stats)

    @patch.dict("os.environ", {"RABBITMQ_PASSWORD": "x"})
    async def test_timeout_returns_none(self):
        client = MagicMock()
        client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        stats = await fetch_queue_stats("apex.tasks", client=client)
        self.assertIsNone(stats)

    @patch.dict("os.environ", {"RABBITMQ_PASSWORD": "x"})
    async def test_malformed_payload_returns_none(self):
        client = MagicMock()
        # Missing fields → int(None) raises TypeError → fail-closed
        client.get = AsyncMock(return_value=_stub_response(200, {"unexpected": "shape"}))
        stats = await fetch_queue_stats("apex.tasks", client=client)
        # When fields are missing, our defaults (0) are still ints, so
        # the response is well-formed zeros.
        self.assertEqual(stats, {"messages_ready": 0, "messages_unacknowledged": 0, "messages": 0})


class SnapshotWorkerMetricsTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_credentials_yields_zeros_and_unreachable(self):
        with patch.dict("os.environ", {"RABBITMQ_PASSWORD": ""}, clear=False):
            snap = await snapshot_worker_metrics()
        self.assertEqual(snap["queue_depth"], 0)
        self.assertEqual(snap["in_flight"], 0)
        self.assertEqual(snap["dlq_size"], 0)
        self.assertFalse(snap["broker_reachable"])

    @patch.dict("os.environ", {"RABBITMQ_PASSWORD": "x"})
    async def test_combines_main_and_dead_queue(self):
        async def fake_fetch(queue_name: str, *, client=None):
            if queue_name == "apex.tasks":
                return {
                    "messages_ready": 4,
                    "messages_unacknowledged": 2,
                    "messages": 6,
                }
            return {
                "messages_ready": 0,
                "messages_unacknowledged": 0,
                "messages": 9,
            }

        with patch("core.rabbitmq_metrics.fetch_queue_stats", side_effect=fake_fetch):
            snap = await snapshot_worker_metrics()
        self.assertEqual(snap["queue_depth"], 4)
        self.assertEqual(snap["in_flight"], 2)
        self.assertEqual(snap["dlq_size"], 9)
        self.assertTrue(snap["broker_reachable"])

    @patch.dict("os.environ", {"RABBITMQ_PASSWORD": "x"})
    async def test_dlq_outage_does_not_blank_main_counters(self):
        async def fake_fetch(queue_name: str, *, client=None):
            if queue_name == "apex.tasks":
                return {
                    "messages_ready": 1,
                    "messages_unacknowledged": 0,
                    "messages": 1,
                }
            return None  # DLQ lookup fails

        with patch("core.rabbitmq_metrics.fetch_queue_stats", side_effect=fake_fetch):
            snap = await snapshot_worker_metrics()
        self.assertEqual(snap["queue_depth"], 1)
        self.assertTrue(snap["broker_reachable"])
        self.assertEqual(snap["dlq_size"], 0)


if __name__ == "__main__":
    unittest.main()
