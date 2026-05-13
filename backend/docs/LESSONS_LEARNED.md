# Backend Lessons Learned

Short notes on bugs that cost real debugging time and how to avoid repeating
them. Keep entries terse — link to the PR for the full fix.

---

## `load_dotenv()` silently misses `backend/.env`

**Symptom.** Every authenticated endpoint (`/analyze/history`,
`/telemetry/history`, `/radio/history`, `/saved-queries`) returned `401
Unauthorized` for a signed-in user. Tokens were valid, `make backend` ran
fine, no exception anywhere.

**Root cause.** `scripts/run-backend.sh` launches `uvicorn` from the repo
root. `python-dotenv`'s bare `load_dotenv()` call walks up from the current
working directory looking for a file literally named `.env`. There is no
`.env` at the repo root — ours lives in `backend/.env` — so dotenv returns
silently without loading anything. Every `os.environ.get("SUPABASE_URL")`
then returned `None`, `_get_jwks_client()` returned `None`, JWKS verify
skipped to the legacy HS256 path which rejected the ES256 token, and the
request fell through to a plain 401.

**What made it hard to see.** `core.auth` fails closed by design — every
verify exception is swallowed and logged at `DEBUG`. Default uvicorn log
level is `INFO`, so the only visible signal was the 401 itself. Worse,
dotenv's `load_dotenv()` never raises when the file is missing; it just
silently no-ops.

**Fix (PR #129).** Pass an explicit path:

```python
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
```

Applied in `core/auth.py`, `core/llm.py`, and `scripts/apply_migrations.py`.

**How to apply next time.**
- Never call `load_dotenv()` with no arguments. Always pass the explicit
  path relative to the module file, not to CWD.
- When an auth path fails closed, temporarily raise its logger to `DEBUG`
  (or add a `print(..., flush=True)` in `_extract_bearer` and
  `_verify_via_jwks`) before assuming the bug is in the token or the
  client. Most "silent 401" bugs are actually missing config.
- If an env var "should" be set but behaves like it isn't, print
  `os.environ.get(VAR)` from inside the running process — not from a fresh
  shell, which may have loaded the env a different way.
