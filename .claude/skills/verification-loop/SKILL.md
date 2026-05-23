---
name: verification-loop
description: Don't claim a task is done until pytest, lint, and the relevant manual demo step have actually passed. Use this skill whenever a task is approaching completion, a commit is about to be made, or you're tempted to say "this should work" — especially after refactors, schema changes, or anything touching backend/frontend integration. The skill enforces a tight evidence-driven loop instead of optimistic completion.
---

# Verification Loop

The cheapest mistake to fix is the one you catch before claiming "done". This skill exists because the failure mode in solo MVP work is *optimistic completion* — saying it works without proof.

## The loop

Repeat until every step passes:

1. **Run** `./.codex/scripts/self-qa.sh --staged`. If it fails, do not interpret — read the actual error message and fix the root cause.
2. **Re-run** the failing step alone (`pytest backend/tests/test_x.py::test_y`, `yarn lint --max-warnings 0`) to confirm the fix is real.
3. **Manual demo** — for any user-visible change, exercise the feature in the browser or hit the API. Type-checks and tests verify *correctness*, not *feature behavior*. If you can't demo it, say so out loud.
4. **Re-stage** anything you fixed (`git add -p` over `git add .` for surgical control).
5. **Repeat from step 1** until the loop is green.

## Forbidden shortcuts

- `--no-verify` on commits.
- Skipping a failing test instead of fixing it.
- Marking a UI task done without opening the browser.
- "It compiles" or "tests pass" without naming which tests.
- Claiming fallback behavior without exercising the fallback path.

## When you genuinely cannot verify

State it explicitly. Examples:

> "I can't verify the live telemetry path because FastF1 cache is empty in this environment — the fallback path is exercised in `tests/test_strategy_helper.py::test_missing_telemetry_returns_fallback`."

That is acceptable. Silence dressed up as success is not.

## Why

A commit that says "it works" but doesn't is more expensive than a commit that says "I verified A and B, didn't verify C" — because future-you trusts the first one and gets ambushed.
