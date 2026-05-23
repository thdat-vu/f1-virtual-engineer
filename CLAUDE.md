# F1 Virtual Engineer — Automation Workflow Guide

## Read first

1. `docs/PROJECT_SPEC.md` — authoritative product direction and architecture.
2. `README.md` — repo overview and current setup.
3. `docs/PROJECT_SPEC_VN.md` — Vietnamese project spec when nuance is needed.
4. `frontend/AGENTS.md` — Next.js version warning before editing frontend code.
5. `.codex/AGENTS.md` — Codex-specific operating guide.

If guidance conflicts, prefer `docs/PROJECT_SPEC.md`, then the actual codebase.

## Product context

This repo is an **indie-hacker MVP** for a solo builder learning and shipping agentic AI on top of Formula 1 data.
Optimize for:

- thin vertical slices,
- fast feedback loops,
- explainable strategy output,
- safe fallbacks when telemetry is missing,
- demoable progress over broad architecture work.

Do not over-engineer. Prefer the smallest change that improves a real user-visible workflow.

## Automation workflow: issue -> implement -> self-QA -> commit -> PR

Follow this sequence for any non-trivial task.

### 1) Intake the issue or task

Capture:

- user outcome,
- business/demo value,
- exact scope,
- non-goals,
- definition of done,
- risky assumptions.

If the task comes from GitHub, inspect the issue first. If no issue exists, treat the user request as the issue statement.

### 2) Start from the correct branch (Git Flow)

Branching rules for this repo:

- `main` = production-ready
- `develop` = integration branch
- `feature/<short-name>` = new feature work
- `bugfix/<short-name>` = non-critical bug fixes
- `hotfix/<short-name>` = urgent production fixes

Workflow:

1. Check current branch.
2. For feature work, branch from `develop`.
3. Never commit directly to `main` or `develop`.
4. Target PRs to `develop` unless the task is a real hotfix.

Suggested commands:

```bash
git checkout develop
git checkout -b feature/<short-name>
```

### 3) Research before implementation

For F1-domain or telemetry work, verify:

- driver code normalization,
- event naming,
- session type mapping (`FP1`, `FP2`, `FP3`, `Q`, `R`, `S`, `SQ`),
- fallback behavior when telemetry is unavailable,
- whether current tests already cover the scenario.

Record assumptions explicitly before coding.

### 4) Design the thinnest acceptable slice

Before editing files, define:

- endpoint or contract change,
- files/modules affected,
- happy path,
- failure path,
- smallest proof of completion.

Preferred MVP shape:

- one backend capability,
- one visible frontend or API surface,
- one focused test/manual verification note.

### 5) Implement in this order

1. schema/contract,
2. tool/helper logic,
3. orchestration/agent logic,
4. API endpoint,
5. frontend wiring,
6. tests.

### 6) Run self-QA before commit

Use the repo-local Codex guardrails:

- `.codex/scripts/self-qa.sh --staged`
- `.codex/scripts/pre-commit-guard.sh`
- `.codex/scripts/commit-msg-guard.sh <commit-msg-file>`

Core checks:

```bash
python3 -m pytest backend/tests
cd frontend && yarn lint
```

Also confirm:

- fallback/error responses are structured,
- claims in strategy output match actual data/heuristics,
- loading/empty/error UI states are reasonable,
- no secrets were added.

### 7) Commit with conventions

Use Conventional Commits with monorepo scopes:

- `feat(backend): add tyre wear prediction fallback metadata`
- `fix(frontend): handle telemetry empty state`
- `docs(repo): update codex workflow guide`

### 8) Open PR using Git Flow

PR rules:

- branch -> `develop` for features/bugfixes,
- title follows conventional commit style,
- body includes summary, why, verification, and follow-ups.

Recommended PR body sections:

- Summary
- Why
- What changed
- Verification
- Risks / follow-ups

## Codex setup in this repo

Tracked Codex assets live in `.codex/`:

- `.codex/AGENTS.md` — project operating guide.
- `.codex/skills/` — repo-specific skills.
- `.codex/scripts/` — reusable guardrail scripts.
- `.codex/git-hooks/` — installable git hook templates.

Install local git hooks with:

```bash
./.codex/scripts/install-git-hooks.sh
```
