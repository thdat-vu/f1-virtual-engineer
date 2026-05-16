## Cursor setup for F1 Virtual Engineer

This `.cursor` setup is adapted from ideas in [everything-claude-code](https://github.com/affaan-m/everything-claude-code) and tuned for this repository's current state:

- Backend: FastAPI + LangGraph skeleton in `backend/`.
- Frontend: Next.js app router dashboard skeleton in `frontend/src/app/`.
- Goal: ship an indie-hacker-friendly MVP fast, while keeping quality and validation loops.

### What is included

- `rules/indie-workflow.md`: lean build-measure-learn workflow.
- `rules/python-fastapi-quality.md`: backend quality gates for API and tools.
- `rules/nextjs-dashboard-quality.md`: frontend quality gates for dashboard UX.
- `skills/f1-mvp-planning/SKILL.md`: feature slicing for race-engineer MVP.
- `skills/f1-strategy-validation/SKILL.md`: telemetry and strategy validation loop.
- `skills/indie-launch-loop/SKILL.md`: weekly launch/feedback loop for solo builders.

### Why these choices

The referenced Affaan post points to a long-form guide emphasizing:

1. token/context optimization,
2. persistent learning loops,
3. verification loops,
4. selective parallelization and subagents.

This setup applies those principles in a lightweight, repo-specific way rather than copying a very large generic template.
