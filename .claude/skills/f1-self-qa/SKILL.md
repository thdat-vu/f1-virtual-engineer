---
name: f1-self-qa
description: Validate telemetry, tyre-wear, pit-window, recommendation, and strategy-explanation changes for plausibility, fallback behavior, explainability, and frontend/API contract integrity before commit or PR. Use this skill whenever changes affect `backend/tools/strategy_helper.py`, `backend/tools/fastf1_helper.py`, `backend/agents/`, telemetry-facing tests, API payloads, or any UI that presents race strategy insight — even for small edits, before saying "this is ready".
---

# F1 Self-QA

Run the repo guardrail script first, then review the five dimensions below. Do not declare a task done until every one is answered yes (or explicitly waived with reason).

## Mechanical check

```bash
./.codex/scripts/self-qa.sh --staged
```

This runs `pytest backend/tests` and `cd frontend && yarn lint && yarn build` only for the surfaces your staged files actually touch. If it fails, fix the root cause — never skip with `--no-verify`.

## 1. Data integrity

- Are driver/session/year inputs normalized correctly?
- Is fallback behavior returned when telemetry is missing — never a synthetic number presented as real?
- Are units and field names consistent with existing schemas?

## 2. Decision plausibility

- Does the pit-window logic align with the degradation signal it claims to use?
- Are undercut/overcut claims tied to explicit gap assumptions?
- Is the confidence level proportional to evidence quality?

## 3. Explainability

The output must answer "why?" in one or two sentences using real metrics, not vague language. If it can't, fix the output before shipping.

## 4. Contract safety

For API/UI changes:

- response fields stay typed and predictable,
- empty / error / loading states are handled,
- new metadata is reflected in tests or the manual verification note.

## 5. Verification log

Write down, in 3-5 lines:

- what was changed,
- what was tested (command + result),
- what was deliberately not tested and why.

This goes into the PR body's **Verification** section.

## Deeper detail

`.codex/skills/f1-strategy-self-qa/SKILL.md` is the canonical long-form version.
