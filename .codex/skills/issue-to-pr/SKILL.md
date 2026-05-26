---
name: issue-to-pr
description: Execute a GitHub issue or repo task from intake through implementation, self-QA, conventional commit, and PR against `develop`. Use when Codex is asked to implement an issue, fix a bug end-to-end, ship a feature, start the next task, prepare a branch/commit/PR, or move work from backlog to merged code in this F1 Virtual Engineer monorepo.
---

# Issue to PR

## Workflow

Run these phases in order.

### 1. Clarify the issue

Restate:

- why this matters,
- scope,
- non-goals,
- definition of done,
- risky assumptions,
- backend/frontend areas affected.

If the task is too large, invoke the `indie-hacker-slice` skill first and reduce it to one thin slice.

### 2. Start from the correct branch

Follow Git Flow:

- branch from `develop`,
- use `feature/<short-name>` for new work,
- use `bugfix/<short-name>` for non-critical fixes,
- use `hotfix/<short-name>` only for urgent production work.

Never commit directly to `main` or `develop`.

### 3. Research before coding

If the task touches telemetry, strategy logic, FastF1, event/session mapping, or F1-domain assumptions, read current code/tests first and use `f1-data-research`.

Capture assumptions explicitly:

- driver codes,
- session type normalization,
- event naming,
- missing-data behavior,
- whether current tests already cover the scenario.

### 4. Design the thinnest acceptable slice

Define:

- files to change,
- contract or schema impact,
- happy path,
- failure path,
- smallest proof that the task is done.

Prefer one vertical slice that is easy to demo.

### 5. Implement in low-risk order

Use this order unless the task clearly requires another sequence:

1. schemas/contracts,
2. helper/tool logic,
3. orchestration/agent logic,
4. API endpoint,
5. frontend wiring,
6. tests.

Keep unrelated refactors out of the issue branch.

### 6. Run self-QA before commit

Run the repo-local guardrails in this order:

1. `./.codex/scripts/self-qa.sh --staged`
2. `./.codex/scripts/pre-commit-guard.sh`
3. make sure commit message will pass `./.codex/scripts/commit-msg-guard.sh`

Also verify:

- fallback responses are structured and honest,
- strategy claims are tied to real metrics or explicit heuristics,
- loading/empty/error states are handled for frontend changes,
- no secrets were introduced.

If the change affects telemetry or strategy behavior, also use `f1-strategy-self-qa`.

If the diff touches strategy/tyre/pit-window heuristics or any code path the
snapshot test exercises, also use `f1-eval-gate` — it codifies the
"regenerate fixtures → run snapshot → only bump `strategy_pit_status.json`
when the heuristic genuinely improves" loop.

If the diff adds, removes, or substantially edits markdown notes under
`backend/rag/corpus/`, or touches the citation retrieval path, also use
`rag-corpus-change` to catch the BM25 regression pattern from #238.

### 7. Commit cleanly

Use Conventional Commits with repo scopes:

- `feat(backend): ...`
- `fix(frontend): ...`
- `docs(repo): ...`
- `test(backend): ...`

### 8. Create the PR

Target `develop` for features and bugfixes.

PR body should include:

- summary,
- why,
- verification performed,
- risks/follow-ups.

## Output format

When using this skill, present:

1. plan,
2. implementation summary,
3. verification log,
4. commit message,
5. PR title/body draft,
6. `ready_for_pr=true/false` with blockers.

## Guardrails

- Do not skip self-QA.
- Do not claim a task is done if tests/lint/manual checks were not run.
- Do not widen scope without telling the user.
- Do not create a PR to `main` for normal feature work.
