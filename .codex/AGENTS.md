# F1 Virtual Engineer — Codex Agent Guide

## Read first

- `docs/PROJECT_SPEC.md`
- `README.md`
- `docs/PROJECT_SPEC_VN.md`
- `frontend/AGENTS.md` before editing Next.js code
- `CLAUDE.md` for the end-to-end automation workflow in this repo

Prefer `docs/PROJECT_SPEC.md` when instructions conflict.

## Product stance

Build for an indie hacker shipping a Virtual F1 Race Engineer MVP.
Prefer:

- thin vertical slices,
- research-first changes,
- explainable outputs,
- safe fallbacks,
- the smallest demoable improvement.

## Codex project structure

- `.codex/skills/` — project skills Codex should use in this repo.
- `.codex/scripts/` — reusable guardrail and self-QA scripts.
- `.codex/git-hooks/` — tracked git-hook templates installable into `.git/hooks/`.

Codex does not rely on `.claude` assets in this repo.
Use `.codex/scripts/install-git-hooks.sh` to activate the local git hooks.

## GitHub MCP in this repo

GitHub MCP is configured in `.codex/config.toml` as `mcp_servers.github`.
Use it when work involves:

- reading or triaging GitHub issues,
- checking PR details or review state,
- preparing PR metadata,
- syncing implementation with GitHub issue context.

Prefer local repo inspection first for code questions, then use GitHub MCP when the task depends on remote issue/PR state or GitHub metadata.

If the GitHub MCP server is configured but not authenticated in the current Codex environment, fall back to local git context or ask the user before relying on remote GitHub operations.

## Codex project skills

| Skill | Use when... |
|---|---|
| `issue-to-pr` | asked to implement an issue/task end-to-end |
| `f1-data-research` | changing FastF1 usage, telemetry assumptions, strategy logic, or F1 domain mapping |
| `f1-strategy-self-qa` | validating telemetry/strategy/API/UI behavior before commit or PR |
| `f1-eval-gate` | changing strategy/tyre/pit-window heuristics — gates `strategy_pit_status.json` updates |
| `rag-corpus-change` | adding/editing markdown notes under `backend/rag/corpus/` or the citation retrieval path |
| `indie-hacker-slice` | reducing large ideas into an MVP-sized slice |

## Required workflow

1. Intake the issue/task and restate why, scope, non-goals, and DoD.
2. Branch from `develop` using Git Flow naming.
3. Research data and domain assumptions first.
4. Design the thinnest acceptable slice.
5. Implement with minimal scope.
6. Run self-QA.
7. Commit using Conventional Commits.
8. Create PR to `develop`.

## Git Flow rules

- Never commit directly to `main` or `develop`.
- New feature: `feature/<short-name>` from `develop`.
- Non-critical fix: `bugfix/<short-name>` from `develop`.
- Urgent production fix: `hotfix/<short-name>`.
- Features and bugfixes should open PRs into `develop`.

## Verification defaults

### Backend

```bash
python3 -m pytest backend/tests
```

### Frontend

```bash
cd frontend && yarn lint
```

### Full slice

```bash
python3 -m pytest backend/tests
cd frontend && yarn lint
```

### Repo guardrails

```bash
./.codex/scripts/self-qa.sh --staged
./.codex/scripts/pre-commit-guard.sh
```

## Guardrails

- Do not pretend telemetry exists if FastF1 data is unavailable.
- Do not present unexplained strategy recommendations.
- Do not skip fallback handling.
- Do not broaden scope without explicit user approval.
- Do not mark issue work complete until self-QA is recorded.
