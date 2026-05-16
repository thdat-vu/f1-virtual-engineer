# F1 Virtual Engineer: Hierarchical Mandates

> Based on ECC (Everything Claude Code) Best Practices.

## L0: Common Instincts (Universal)
- **Research-First**: Never edit a file without searching for usage patterns first.
- **Surgical Edits**: Prefer `replace` over `write_file`. Minimize diff noise.
- **Continuous Verification**: Run relevant tests immediately after ANY change.
- **Self-Correction**: If a tool fails, diagnose the error before retrying. Do not "brute force".

## L1: Ecosystem Standards
### Backend (Python/FastAPI/LangGraph)
- Strict type hinting (Pydantic V2).
- Async-first for all I/O bound operations.
- State-machine consistency (Check versioning).
### Frontend (React/Next.js/Zustand)
- No `any`. Strict TypeScript interfaces.
- Component Atomic Design (Surgical UI).
- State isolation via Zustand selectors.

## L2: Project Apex (Specific)
- **FastF1 Integrity**: Use `backend/data` cache. No hallucinations on driver data.
- **Racing Aesthetic**: Apple x Automotive (True black, monumental type).
- **Indie Speed**: Smallest shippable slice first.

## L3: Verification Gate (DoD)
1. Code implements requirement.
2. 80%+ test coverage for new logic.
3. Lint/Type-check passes (`npm run build` for frontend).
4. Documentation updated.
