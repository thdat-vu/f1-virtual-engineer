---
name: f1-eval-gate
description: Use when changing strategy/tyre/pit-window heuristics or thresholds in `backend/tools/strategy_helper.py`, `backend/tools/tyre_helper.py`, or any code path the snapshot test exercises. Codifies the eval-driven loop: regenerate fixtures → run snapshot mode → adjust `strategy_pit_status.json` only if the heuristic genuinely improved AND the snapshot is regenerated.
---

# F1 Eval Gate

The strategy heuristic is gated in CI by a snapshot test that derives ground truth from FastF1 lap data. The pass count and total live in `backend/evals/cases/strategy_pit_status.json` — the same file the landing page reads. A change that drifts the snapshot count must update the JSON and regenerate the groundtruth in lockstep.

## When to use

Trigger this skill before opening a PR if the diff touches any of:

- `backend/tools/strategy_helper.py` (pit-window, undercut, or tyre-tier logic),
- `backend/tools/tyre_helper.py` (degradation features),
- `backend/agents/race_engineer.py` strategy paths,
- the snapshot fixtures or groundtruth JSON.

## Workflow

### 1. Confirm the baseline

Run snapshot mode against the unchanged code to record the current pass count.

```bash
STRATEGY_PIT_EVAL_SNAPSHOT=1 python3 -m pytest backend/tests/test_strategy_pit_eval.py -q
```

Read `backend/evals/cases/strategy_pit_status.json` and note `passing/total`.

### 2. Apply the heuristic change

Keep the diff focused on the heuristic — no unrelated refactors.

### 3. Re-run snapshot mode

```bash
STRATEGY_PIT_EVAL_SNAPSHOT=1 python3 -m pytest backend/tests/test_strategy_pit_eval.py -q
```

Three outcomes:

- **Pass count unchanged** — no JSON update needed, ship the change.
- **Pass count increased** — bump `passing` (and `last_updated`) in `strategy_pit_status.json`. The threshold is sticky: any future drop now trips CI.
- **Pass count decreased** — do *not* lower the threshold. Either fix the heuristic or roll back. Lowering the gate to make CI green is the failure mode this skill exists to prevent.

### 4. Regenerate groundtruth (live mode) only when fixtures change

If you added/removed a fixture, regenerate the groundtruth snapshot using live FastF1 data:

```bash
RUN_STRATEGY_PIT_EVAL=1 python3 -m pytest backend/tests/test_strategy_pit_eval.py -q
```

This requires the FastF1 cache under `backend/data/`. CI does not run this — it stays a local-only step.

### 5. Update both numbers atomically

If `passing` moves, update `passing` and `last_updated` together. The total only changes when fixtures change, never as part of a heuristic tweak.

## Output format

Report:

- baseline pass count (before),
- new pass count (after),
- JSON updated? (yes/no, with reason),
- whether groundtruth regeneration was needed.

## Guardrails

- Never lower `passing` to silence a regression — that is the failure mode this gate exists to catch.
- Never edit `strategy_pit_status.json` without re-running the snapshot test.
- Keep `passing/total` and the README/landing claims consistent — the JSON is the single source of truth.
- If the heuristic improvement is intentional but only on one fixture, the threshold can stay. Bump only when the new floor is genuinely defensible.
