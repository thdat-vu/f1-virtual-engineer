---
name: f1-issue-to-pr
description: Run a GitHub issue or repo task end-to-end in this F1 Virtual Engineer monorepo — from intake, branching, research, thin-slice design, implementation, self-QA, conventional commit, to PR against `develop`. Use this skill whenever the user asks to implement an issue, fix a bug end-to-end, ship a feature, start the next task, prepare a branch/commit/PR, or move backlog work to merged code — even if they don't explicitly say "issue-to-pr".
---

# F1 Issue to PR

Drive the workflow described in the repo's top-level `CLAUDE.md` end-to-end. The phases are non-negotiable; the depth of each phase scales with task size.

## Phase 1 — Intake

Restate, in your own words:

- user outcome,
- why it matters now,
- exact scope,
- non-goals,
- definition of done,
- risky assumptions.

If the task came from GitHub, fetch the issue first (`gh issue view <n>`). If it didn't, treat the user request as the issue.

If the task is too broad, invoke the `indie-hacker-slice` skill before continuing.

## Phase 2 — Branch (Git Flow)

Branching rules:

- `main` = production-ready
- `develop` = integration
- `feature/<short-name>` from `develop` for new work
- `bugfix/<short-name>` from `develop` for non-critical fixes
- `hotfix/<short-name>` only for urgent production fixes

Never commit directly to `main` or `develop`. PRs target `develop` unless the task is a real hotfix.

```bash
git checkout develop && git pull
git checkout -b feature/<short-name>
```

## Phase 3 — Research before coding

If the task touches FastF1, telemetry, strategy logic, session/event mapping, or any F1-domain claim, invoke `f1-data-research` before editing code. Record assumptions explicitly — do not invent telemetry behavior.

## Phase 4 — Design the thinnest acceptable slice

Before editing files, define:

- endpoint or contract change,
- files/modules affected,
- happy path,
- failure path,
- smallest proof of completion.

Preferred shape: one backend capability + one visible frontend/API surface + one focused test or manual verification note.

## Phase 5 — Implement in this order

1. schema/contract,
2. tool/helper logic,
3. orchestration/agent logic,
4. API endpoint,
5. frontend wiring,
6. tests.

## Phase 6 — Self-QA

Run the `/qa` command (or invoke `f1-self-qa` skill). Do not move to commit until it passes and you've confirmed:

- fallback/error responses are structured,
- strategy claims match real heuristics, not vibes,
- loading/empty/error UI states are handled,
- no secrets were added.

## Phase 7 — Commit

Conventional Commits with monorepo scopes:

- `feat(backend): add tyre wear prediction fallback metadata`
- `fix(frontend): handle telemetry empty state`
- `docs(repo): update workflow guide`

**No AI attribution.** Never append `Co-Authored-By: Claude`, `🤖 Generated with Claude Code`, or any equivalent line to commit messages or PR bodies in this repo. The repo owner removes them every time; just skip them at the source.

## Phase 8 — PR

Open the PR against `develop` with sections: **Summary**, **Why**, **What changed**, **Verification**, **Risks / follow-ups**. Use `gh pr create` with a HEREDOC body. Same no-AI-attribution rule applies — no trailing "Generated with…" line in the description.

## Deeper detail

For the codex-mirrored long-form version of this workflow, see `.codex/skills/issue-to-pr/SKILL.md` and the top-level `CLAUDE.md` — both are authoritative.
