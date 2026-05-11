"""Tests for the FastF1 pre-bake mechanism (#100 slice C)."""

from __future__ import annotations

import gzip
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tools import fastf1_helper
from tools.fastf1_helper import (
    _reset_caches_for_tests,
    _stable_key_digest,
    get_event_drivers,
    get_year_schedule,
    load_prebaked_into_caches,
)


class PrebakeRoundTripTests(unittest.TestCase):
    """Recording in one process + loading in a fresh state behaves like a hit."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._original_dir = fastf1_helper.PREBAKE_DIR
        fastf1_helper.PREBAKE_DIR = self._tmp.name
        os.environ["FASTF1_PREBAKE_WRITE"] = "true"
        _reset_caches_for_tests()

    def tearDown(self) -> None:
        fastf1_helper.PREBAKE_DIR = self._original_dir
        os.environ.pop("FASTF1_PREBAKE_WRITE", None)
        self._tmp.cleanup()

    def test_schedule_record_then_replay(self):
        fake_schedule = MagicMock()
        fake_schedule.iterrows.return_value = iter([
            (0, {"EventName": "Monza", "Location": "Monza", "RoundNumber": 16, "OfficialEventName": "GP"}),
        ])
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=fake_schedule) as mock_get:
            recorded = get_year_schedule(2024)

        # Wipe in-memory cache to simulate a fresh process start.
        _reset_caches_for_tests()

        # Load from disk; the prior result should be re-seeded.
        loaded_count = load_prebaked_into_caches()
        self.assertGreaterEqual(loaded_count, 1)

        # Subsequent call must hit the cache (no new fastf1 invocation).
        with patch.object(fastf1_helper.fastf1, "get_event_schedule") as mock_get2:
            replayed = get_year_schedule(2024)
        mock_get2.assert_not_called()
        self.assertEqual(replayed, recorded)

    def test_record_writes_gzipped_json(self):
        fake_schedule = MagicMock()
        fake_schedule.iterrows.return_value = iter([
            (0, {"EventName": "Imola", "Location": "Imola", "RoundNumber": 6, "OfficialEventName": "GP"}),
        ])
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=fake_schedule):
            get_year_schedule(2023)

        subdir = os.path.join(fastf1_helper.PREBAKE_DIR, "schedule")
        self.assertTrue(os.path.isdir(subdir))
        files = [f for f in os.listdir(subdir) if f.endswith(".json.gz")]
        self.assertEqual(len(files), 1)

        with gzip.open(os.path.join(subdir, files[0]), "rt", encoding="utf-8") as fh:
            entry = json.load(fh)
        self.assertEqual(entry["args"], [2023])
        self.assertEqual(entry["kwargs"], {})
        self.assertEqual(entry["result"][0]["name"], "Imola")

    def test_recording_disabled_by_default_does_not_write(self):
        os.environ.pop("FASTF1_PREBAKE_WRITE", None)
        fake_schedule = MagicMock()
        fake_schedule.iterrows.return_value = iter([
            (0, {"EventName": "Spa", "Location": "Spa", "RoundNumber": 12, "OfficialEventName": "GP"}),
        ])
        with patch.object(fastf1_helper.fastf1, "get_event_schedule", return_value=fake_schedule):
            get_year_schedule(2022)
        # No files should have been written.
        subdir = os.path.join(fastf1_helper.PREBAKE_DIR, "schedule")
        if os.path.isdir(subdir):
            self.assertEqual(os.listdir(subdir), [])

    def test_fallback_results_not_persisted(self):
        with patch.object(fastf1_helper.fastf1, "get_session", side_effect=RuntimeError("net")):
            r = get_event_drivers(year=2024, event="Imola")
        self.assertTrue(r["fallback"])
        subdir = os.path.join(fastf1_helper.PREBAKE_DIR, "roster")
        if os.path.isdir(subdir):
            self.assertEqual([f for f in os.listdir(subdir) if f.endswith(".json.gz")], [])

    def test_load_handles_missing_dir(self):
        # Point at a path that doesn't exist; loader must return 0, not raise.
        fastf1_helper.PREBAKE_DIR = os.path.join(self._tmp.name, "does-not-exist")
        self.assertEqual(load_prebaked_into_caches(), 0)

    def test_load_skips_corrupt_files(self):
        bad_dir = os.path.join(fastf1_helper.PREBAKE_DIR, "schedule")
        os.makedirs(bad_dir, exist_ok=True)
        with open(os.path.join(bad_dir, "broken.json.gz"), "wb") as fh:
            fh.write(b"not a real gzip file")
        # Should not raise. Returns whatever it managed (0 here).
        self.assertEqual(load_prebaked_into_caches(), 0)


class StableKeyTests(unittest.TestCase):
    def test_kwarg_order_does_not_affect_digest(self):
        d1 = _stable_key_digest((), {"year": 2024, "event": "Monza"})
        d2 = _stable_key_digest((), {"event": "Monza", "year": 2024})
        self.assertEqual(d1, d2)

    def test_different_args_yield_different_digests(self):
        d1 = _stable_key_digest((2024,), {})
        d2 = _stable_key_digest((2023,), {})
        self.assertNotEqual(d1, d2)


if __name__ == "__main__":
    unittest.main()
