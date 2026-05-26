---
name: rag-corpus-change
description: "Use when adding, removing, or substantially editing markdown notes under `backend/rag/corpus/`, or when changing the citation retrieval path in `backend/tools/knowledge_retriever.py` / `backend/agents/race_engineer.py`. Codifies the regression check learned from #238 — generic year/race vocabulary in new notes can outscore topical strategy notes at low `k`, breaking the citation contract for natural-language pit questions."
---

# RAG Corpus Change

The citation system uses BM25 over `backend/rag/corpus/*.md`. Adding notes shifts the score distribution — a new note with year tokens or driver codes can outscore a topical strategy note for queries like "should HAM undercut now in japan 2023 race". This skill exists because that exact regression happened in #238 and was fixed by bumping `knowledge_lookup` k from 2 to 3 in `backend/agents/race_engineer.py`.

## When to use

Trigger this skill if the diff:

- adds or removes any file under `backend/rag/corpus/`,
- meaningfully edits the body of an existing note (new vocabulary, expanded scope),
- changes the `k` parameter or scoring path in `backend/tools/knowledge_retriever.py`,
- changes how `race_engineer.py` calls `knowledge_lookup`.

Skip for typo-only edits.

## Workflow

### 1. Run the citation regression suite first

```bash
python3 -m pytest backend/tests/test_race_engineer.py -q
python3 -m pytest backend/tests/test_knowledge_retriever.py -q
```

Confirm green on the unchanged corpus.

### 2. Apply the corpus change

Keep frontmatter consistent — `id`, `title`, `source`, `section`, `topics`. The `topics` list drives recall on natural-language queries; underspecified topics is a common cause of low BM25 score on the right note.

### 3. Re-run the citation tests

```bash
python3 -m pytest backend/tests/test_race_engineer.py -q
```

Pay special attention to `test_analyze_query_attaches_citations_for_strategy_intent` and equivalents — these assert that natural-language strategy queries land on a topical strategy note, not a generic car/regulation note.

### 4. If a strategy-intent test now lands on the wrong note

Three options, ranked:

1. **Tighten the new note's vocabulary.** Drop years or driver codes from the body if they're incidental — the score on cross-year notes was the lever in #238.
2. **Bump the topical note's `topics` frontmatter.** If `strategy-undercut` should win on "undercut" queries, make sure that token actually appears in the topical note.
3. **Last resort: bump `k` in `race_engineer.py`.** This widens the citation slate so a topical note still appears even if it's not first. #238 used this — note the comment explains the trade-off in plain English so the next person doesn't think `k=3` is arbitrary.

Do not silently rewrite the test query to make the test pass.

### 5. Manual smoke

For 2–3 representative natural-language queries the user might ask, hit `/knowledge/lookup` (or the citation path inside `/analyze`) and confirm the top result is reasonable.

## Output format

Report:

- which corpus files changed,
- citation tests before vs after,
- whether `k` or any retrieval parameter moved (with reason),
- top-3 results for at least one strategy query and one car/regulation query.

## Guardrails

- Never raise `k` without a recorded reason in the call site comment.
- Never delete a note just to silence a regression — fix the topic vocabulary first.
- Never add a note whose body content overlaps the existing corpus without checking BM25 ranking first.
- The corpus is part of the explainability contract — a wrong citation is worse than no citation.
