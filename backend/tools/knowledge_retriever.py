"""Lightweight BM25-backed FIA knowledge retriever.

The corpus lives as markdown files under ``backend/rag/corpus/``. Each file
starts with a YAML-ish frontmatter block (``id``, ``title``, ``source``,
``section``, ``topics``) followed by the snippet body. We parse the
frontmatter with a small regex — no ``pyyaml`` dep needed for 5 files.

BM25 indexing happens once at module import; ``lookup`` is a pure in-memory
ranking call, so the endpoint stays sub-millisecond.
"""

from __future__ import annotations

import logging
import re
import string
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

_logger = logging.getLogger(__name__)

CORPUS_DIR = Path(__file__).resolve().parent.parent / "rag" / "corpus"

_FRONTMATTER_RE = re.compile(r"^---\n(?P<meta>.*?)\n---\n(?P<body>.*)$", re.DOTALL)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class CorpusEntry:
    id: str
    title: str
    source: str
    section: str
    topics: tuple[str, ...]
    body: str


def _parse_frontmatter(raw: str) -> dict[str, Any]:
    """Parse a tiny subset of YAML: `key: value` and `key: [a, b]` lists."""
    out: dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
            out[key] = items
        else:
            out[key] = value.strip("\"'")
    return out


def _load_corpus(corpus_dir: Path) -> list[CorpusEntry]:
    entries: list[CorpusEntry] = []
    if not corpus_dir.exists():
        _logger.warning("knowledge corpus directory missing: %s", corpus_dir)
        return entries
    for path in sorted(corpus_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(text)
        if not match:
            _logger.warning("corpus file missing frontmatter, skipping: %s", path.name)
            continue
        meta = _parse_frontmatter(match.group("meta"))
        body = match.group("body").strip()
        entries.append(
            CorpusEntry(
                id=str(meta.get("id") or path.stem),
                title=str(meta.get("title") or path.stem),
                source=str(meta.get("source") or ""),
                section=str(meta.get("section") or ""),
                topics=tuple(meta.get("topics") or ()),
                body=body,
            )
        )
    return entries


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@lru_cache(maxsize=1)
def _index(corpus_path: str = str(CORPUS_DIR)) -> tuple[BM25Okapi, tuple[CorpusEntry, ...]]:
    entries = _load_corpus(Path(corpus_path))
    if not entries:
        # BM25Okapi requires at least one document; return a sentinel empty index.
        return BM25Okapi([["_"]]), ()
    docs = [
        _tokenize(f"{e.title} {' '.join(e.topics)} {e.section} {e.body}")
        for e in entries
    ]
    return BM25Okapi(docs), tuple(entries)


def _snippet(body: str, limit: int = 260) -> str:
    body = body.strip()
    if len(body) <= limit:
        return body
    cut = body.rfind(" ", 0, limit)
    return f"{body[: cut if cut > 0 else limit].rstrip(string.punctuation + ' ')}…"


def lookup(query: str, k: int = 3) -> list[dict[str, Any]]:
    """Return the top-`k` corpus entries for a natural-language query."""
    k = max(1, min(k, 10))
    bm25, entries = _index()
    if not entries:
        return []
    tokens = _tokenize(query)
    if not tokens:
        return []
    scores = bm25.get_scores(tokens)
    ranked = sorted(
        ((float(score), entry) for score, entry in zip(scores, entries)),
        key=lambda pair: pair[0],
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for score, entry in ranked[:k]:
        if score <= 0.0:
            continue
        out.append(
            {
                "id": entry.id,
                "title": entry.title,
                "source": entry.source,
                "section": entry.section,
                "topics": list(entry.topics),
                "snippet": _snippet(entry.body),
                "score": round(score, 4),
            }
        )
    return out


def reset_index_cache() -> None:
    """Test helper — force the BM25 index to reload on next lookup."""
    _index.cache_clear()


def get_note(note_id: str) -> dict[str, Any] | None:
    """Return a single corpus entry by id with the full body, or None if missing.

    Used by ``GET /knowledge/note/{id}`` so the frontend can show the whole
    note in a popover after a citation chip is clicked. ``lookup`` returns
    a truncated ``snippet``; this returns the untruncated ``body`` so the
    UI never has to refetch the corpus file itself.
    """
    if not note_id:
        return None
    _, entries = _index()
    for entry in entries:
        if entry.id == note_id:
            return {
                "id": entry.id,
                "title": entry.title,
                "source": entry.source,
                "section": entry.section,
                "topics": list(entry.topics),
                "body": entry.body,
            }
    return None
