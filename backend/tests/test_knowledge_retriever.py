import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests._helpers import reset_rate_limiter
from tools.knowledge_retriever import (
    CORPUS_DIR,
    _parse_frontmatter,
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

    def test_lookup_respects_k(self):
        hits = lookup("safety car restart tyre compound drs", k=2)
        self.assertLessEqual(len(hits), 2)

    def test_lookup_empty_query_returns_empty(self):
        self.assertEqual(lookup(""), [])
        self.assertEqual(lookup("!!!"), [])


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


if __name__ == "__main__":
    unittest.main()
