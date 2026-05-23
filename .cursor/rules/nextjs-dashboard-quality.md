---
description: "Next.js dashboard quality standards for telemetry UX"
alwaysApply: true
---

# Next.js Dashboard Quality Rule

Applies to files in `frontend/`.

## UI priorities for MVP

- Optimize for clarity of race decisions, not visual complexity.
- Every dashboard card should answer one question (pace, tyre wear, pit window, threat).
- Keep placeholder sections clearly marked until connected to backend data.

## Data contract discipline

- Type API responses with explicit TypeScript interfaces.
- Handle loading, empty, and error states for all backend-driven widgets.
- Avoid hardcoded sample values in production paths once API integration exists.

## Performance and maintainability

- Keep page-level components lean; extract reusable card components when duplication starts.
- Avoid unnecessary client-only rendering for static sections.
- Keep class names and structure readable; prefer consistent spacing and naming.

## Validation checklist

Before considering a frontend task done:

1. `yarn lint` passes.
2. Main route renders with no runtime errors.
3. At least one interaction path is tested manually (driver select, strategy panel update, or equivalent).
