import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests._helpers import reset_rate_limiter
from tools.knowledge_retriever import (
    CORPUS_DIR,
    _parse_frontmatter,
    get_note,
    lookup,
    reset_index_cache,
)


class KnowledgeRetrieverTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        reset_index_cache()

    def test_corpus_directory_populated_with_markdown(self):
        files = sorted(CORPUS_DIR.glob("*.md"))
        self.assertGreaterEqual(len(files), 5, "expected at least 5 curated FIA snippets")
        for path in files:
            self.assertTrue(path.read_text(encoding="utf-8").startswith("---\n"), f"{path.name} missing frontmatter")

    def test_parse_frontmatter_supports_scalar_and_list(self):
        meta = _parse_frontmatter(
            "id: x\ntitle: Example rule\ntopics: [safety-car, restart]"
        )
        self.assertEqual(meta["id"], "x")
        self.assertEqual(meta["title"], "Example rule")
        self.assertEqual(meta["topics"], ["safety-car", "restart"])

    def test_lookup_drs_returns_drs_entry(self):
        hits = lookup("DRS activation rules")
        self.assertTrue(hits, "expected at least one DRS match")
        self.assertEqual(hits[0]["id"], "drs-activation")
        self.assertGreater(hits[0]["score"], 0.0)
        self.assertIn("overtaking", hits[0]["topics"])
        self.assertTrue(hits[0]["snippet"])

    def test_lookup_yellow_flag_returns_yellow_entry(self):
        hits = lookup("yellow flag driver obligations")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "yellow-flag")

    def test_lookup_pit_lane_returns_pit_entry(self):
        hits = lookup("pit lane speed limit penalty")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "pit-lane-speed")

    def test_lookup_undercut_returns_strategy_entry(self):
        hits = lookup("should I undercut now to gain track position")
        self.assertTrue(hits, "expected at least one strategy hit")
        self.assertEqual(hits[0]["id"], "strategy-undercut")
        self.assertIn("undercut", hits[0]["topics"])

    def test_lookup_safety_car_pit_window_prefers_strategy_entry(self):
        # The FIA "safety-car" entry covers procedure; the strategy entry
        # covers the pit-window decision. A strategy-shaped query should
        # surface the strategy snippet ahead of the rules text.
        hits = lookup("safety car pit window — should we pit now to save time")
        self.assertTrue(hits)
        ids = [h["id"] for h in hits]
        self.assertIn("strategy-sc-pit-window", ids)
        self.assertEqual(ids[0], "strategy-sc-pit-window")

    def test_lookup_tyre_cliff_returns_strategy_entry(self):
        hits = lookup("rear tyre cliff degradation lap time falling off")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "strategy-tyre-cliff")

    def test_lookup_respects_k(self):
        hits = lookup("safety car restart tyre compound drs", k=2)
        self.assertLessEqual(len(hits), 2)

    def test_lookup_empty_query_returns_empty(self):
        self.assertEqual(lookup(""), [])
        self.assertEqual(lookup("!!!"), [])

    def test_get_note_returns_full_body_for_existing_id(self):
        note = get_note("strategy-undercut")
        self.assertIsNotNone(note)
        assert note is not None  # type narrow for mypy/pylance
        self.assertEqual(note["id"], "strategy-undercut")
        self.assertIn("undercut", note["topics"])
        # Body must be the untruncated text — longer than the lookup snippet limit (260).
        self.assertGreater(len(note["body"]), 260)
        self.assertNotIn("…", note["body"])

    def test_get_note_returns_none_for_unknown_id(self):
        self.assertIsNone(get_note("does-not-exist"))
        self.assertIsNone(get_note(""))


class KnowledgeLookupEndpointTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        reset_index_cache()
        self.client = TestClient(app)

    def test_endpoint_returns_citations(self):
        res = self.client.post("/knowledge/lookup", json={"query": "pit lane speed", "k": 2})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["query"], "pit lane speed")
        self.assertGreaterEqual(len(body["citations"]), 1)
        self.assertLessEqual(len(body["citations"]), 2)
        top = body["citations"][0]
        for key in ("id", "title", "source", "section", "topics", "snippet", "score"):
            self.assertIn(key, top)
        self.assertEqual(top["id"], "pit-lane-speed")

    def test_endpoint_validates_k_range(self):
        too_low = self.client.post("/knowledge/lookup", json={"query": "drs", "k": 0})
        self.assertEqual(too_low.status_code, 422)
        too_high = self.client.post("/knowledge/lookup", json={"query": "drs", "k": 11})
        self.assertEqual(too_high.status_code, 422)

    def test_endpoint_validates_query_length(self):
        short = self.client.post("/knowledge/lookup", json={"query": "x"})
        self.assertEqual(short.status_code, 422)

    def test_endpoint_openapi_registration(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/knowledge/lookup", schema["paths"])
        operation = schema["paths"]["/knowledge/lookup"]["post"]
        self.assertIn("knowledge", operation["tags"])


class KnowledgeNoteEndpointTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limiter()
        reset_index_cache()
        self.client = TestClient(app)

    def test_endpoint_returns_full_body_for_existing_id(self):
        res = self.client.get("/knowledge/note/strategy-undercut")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "success")
        note = body["note"]
        self.assertEqual(note["id"], "strategy-undercut")
        self.assertIn("undercut", note["topics"])
        # Untruncated body — longer than the snippet limit used by /lookup.
        self.assertGreater(len(note["body"]), 260)

    def test_endpoint_returns_404_for_missing_id(self):
        res = self.client.get("/knowledge/note/does-not-exist")
        self.assertEqual(res.status_code, 404)
        body = res.json()
        self.assertEqual(body["status"], "error")
        self.assertIsNone(body["note"])
        self.assertIn("not found", body["error"])

    def test_endpoint_openapi_registration(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/knowledge/note/{note_id}", schema["paths"])
        operation = schema["paths"]["/knowledge/note/{note_id}"]["get"]
        self.assertIn("knowledge", operation["tags"])


if __name__ == "__main__":
    unittest.main()
