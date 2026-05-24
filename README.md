# F1 Virtual Engineer

[![CI](https://github.com/thdat-vu/f1-virtual-engineer/actions/workflows/ci.yml/badge.svg)](https://github.com/thdat-vu/f1-virtual-engineer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![Yarn](https://img.shields.io/badge/Yarn-4-2C8EBB?logo=yarn&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

An end-to-end agentic AI system that acts as a virtual Formula 1 race engineer. It processes telemetry, retrieves historical race data, and produces strategy recommendations — pit-stop timing (undercut/overcut), tire-degradation analysis, explainable race calls.

---

## System Architecture

The project follows a robust, production-ready agentic workflow separating business logic from AI execution:

* **Frontend (Next.js Dashboard):** A real-time interface displaying telemetry charts and the agent's reasoning traces.
* **Backend API (FastAPI):** Chosen because FastAPI is fast to develop, supports async, has strong typing via Pydantic, and generates OpenAPI docs[cite: 303].
* **Agent Orchestrator (LangGraph):** Manages multi-agent coordination. It models agent behavior as a graph with nodes (steps) and edges (transitions), which is easier to reason about than implicit loops.
* **Data Connectors:** Custom Python wrappers for the `FastF1` library to extract speed, throttle, brake, and tire data.
* **RAG System:** BM25 keyword retrieval over a curated markdown corpus (`backend/rag/corpus/*.md`) — FIA regulation snippets and F1 strategy concepts (undercut, overcut, SC pit window, tyre cliff, …). Citations are injected into the rationale prompt and surfaced as click-able chips in Mission Control. No vector DB on purpose for the MVP — keeps infra cost at zero and the corpus auditable in version control.

---

## Repository Structure

To ensure maintainability and scalability, this project uses a monorepo structure:

* **`backend/`**: Logic Agentic AI (FastAPI + LangGraph)
    * `app/`: API entry points, router configuration.
    * `agents/`: Agent graphs (Nodes, Edges, State).
    * `core/`: System Prompts, core logic, and policies.
    * `tools/`: FastF1 API wrappers with Pydantic schemas.
    * `rag/`: Chunking and retrieval for historical data.
    * `eval/`: Golden sets and evaluation scripts.
    * `infra/`: Docker, environment variables, and config.
* **`frontend/`**: Next.js Dashboard for real-time visualization.
* **`docker-compose.staging.yml`**: Staging-like containerization (api + frontend + redis + rabbitmq + celery worker + dlq-worker). See "Staging-like Docker Compose" below.
* **`Makefile`**: One-shot dev helpers — `make dev`, `make redis-up`, `make stack-up`, etc.

---

## Tech Stack

* **Language:** Python 3.11+ (Backend) & TypeScript (Frontend)
* **AI Orchestration:** LangGraph, LangChain
* **API Framework:** FastAPI, Pydantic
* **Telemetry Data:** FastF1 (numpy-aligned distance grids for lap-vs-lap Δt)
* **Frontend:** Next.js 16 (App Router, Turbopack), framer-motion, Yarn 4 (corepack-pinned, immutable installs)
* **Auth + Persistence:** Supabase Auth (Google OAuth, asymmetric JWT/JWKS), Supabase Postgres with row-level security
* **Caching:** `cachetools` TTLCache (L1, in-process) + optional Redis (L2, shared across workers)
* **Async pipeline:** Celery + RabbitMQ (opt-in async LLM rationale path with bounded retries + dead-letter queue)
* **Deployment:** Docker, Docker Compose (staging stack hardened — no host port mapping for Redis/RabbitMQ, renamed `CONFIG`/`FLUSHALL`, `requirepass` enforced)

---

## Core Agent Capabilities

The Virtual Engineer is equipped with strict tool-use policies and capabilities. Shipped capabilities are exposed as endpoints today; pending ones are tracked in [open issues](https://github.com/thdat-vu/f1-virtual-engineer/issues).

| Capability | Status | Endpoint |
| --- | --- | --- |
| `get_telemetry` — speed/gear/RPM/throttle/brake summaries with fallback metadata | ✅ Shipped | `GET /telemetry`, `GET /laps/{...}` |
| `strategy_analyzer` — pit-window recommendations with undercut/overcut risk, confidence band, real FastF1 gap to a chosen rival, per-track pit-loss table, undercut break-even laps, and expected-gain projection over a 3-lap rival reaction window (#168) | ✅ Shipped | `POST /analyze` (strategy intent — explicit `Telemetry / Strategy` toggle in Mission Control) |
| `lap_delta` — per-distance Δt(reference vs compare) computed by aligning two drivers' fastest-lap telemetry on a shared distance grid (`numpy.interp`), so the chart shows *where* on the lap the gap actually accrues, not just the final number | ✅ Shipped | `POST /lap-delta` |
| `race_engineer_rationale` — Gemini Flash-generated natural-language summary, with deterministic template fallback when the LLM is unavailable. Optional async path (`RATIONALE_ASYNC=true`) returns the template instantly and back-fills the LLM rationale onto the persisted history row via a Celery worker — the frontend swaps the text in once it lands. | ✅ Shipped | `POST /analyze` (`rationale_source: "llm" \| "template"`, `analyze_history_id`, `rationale_job_id`) |
| `radio_interpreter` — closed-set classification of team-radio transcripts (tyre/brake/engine/traffic/weather/strategy/none) with severity + trigger phrase | ✅ Shipped | `POST /radio/analyze` |
| `predict_tyre_wear` — standalone tyre-degradation snapshot with compound, stint length, observed decay (s/lap), projected cliff-lap, and an `as of L<n>` context line so the headline can't be misread as a real-time call about the lap currently on screen | ✅ Shipped | `POST /tyre/analyze` |
| `knowledge_retriever` — BM25 retrieval over a curated FIA regulations + F1 strategy-concepts corpus (undercut, overcut, SC pit window, tyre cliff, …). Citations are injected into the rationale prompt so the LLM grounds its call in named patterns instead of generic prose, and surfaced as click-able chips in Mission Control with a popover for the full note body. | ✅ Shipped | `POST /knowledge/lookup`, `GET /knowledge/note/{id}`; citations also ride alongside `POST /analyze` |
| Google sign-in (Supabase Auth foundation) | ✅ Shipped | `/auth/callback` (frontend) |
| Per-user `/analyze` history — opt-in persistence by session, list endpoint, Mission Control "Recent" panel. Clicking a row replays the analysis so the chart panels populate immediately (cache-warm hit ≈50ms). | ✅ Shipped | `POST /analyze` (writes when JWT present), `GET /analyze/history` |
| Per-user `/telemetry` history — opt-in persistence by session, list endpoint, Mission Control "Recently viewed" panel. Clicking a row auto-replays the analyze for that session. | ✅ Shipped | `POST /telemetry` (writes when JWT present), `GET /telemetry/history` |
| Per-user radio history + saved/favorited queries — Star button next to Analyze persists the current selection (driver, session, optional `vs <driver>` comparison) and the Saved panel restores the full state on click. | ✅ Shipped | `POST /radio/analyze` writes radio rows; `GET/POST/DELETE /saved-queries` for saved queries |

### Reliability features already in production

* **Rate limiting** — `slowapi` token-bucket on the LLM and telemetry routes; structured 429 envelope with `retry_after_seconds` and a `Retry-After` header.
* **Fail-closed LLM path** — every Gemini call is wrapped so a missing key, timeout, or malformed response degrades to a deterministic fallback rather than a 500.
* **In-memory response cache (60 s TTL)** — repeated identical LLM calls are served from a SHA-256-keyed cache, namespaced by call type.
* **FastF1 result cache + threadpool offload** — schedule/roster/lap-list responses are cached in-process for 24 h, telemetry summaries + tyre features for 1 h. Fallback/empty results are *not* cached, so a transient FastF1 hiccup never sticks. Helper calls now run on the FastAPI threadpool (`asyncio.to_thread`) so a slow FastF1 fetch no longer blocks the event loop for concurrent requests.
* **Pre-baked cache warmup** — `backend/scripts/prebake.py` records helper outputs to `backend/data/prebake/<helper>/*.json.gz`. On startup the FastAPI lifespan hook seeds the in-process TTLCaches from those snapshots, so the first user after a restart hits warm-cache latency for the demo session set instead of paying the multi-second FastF1 cold load.
* **Optional Redis L2 cache** — set `REDIS_URL` (e.g. `redis://localhost:6379/0`) and the FastF1 helpers gain a second tier: L1 in-process → L2 Redis → compute. Multi-worker / multi-pod deployments share the same warmed-up state instead of each process refilling its own cache. A Redis outage degrades silently to "L1 only" — the API never 5xxs because of cache infrastructure. Inspect `GET /metrics` → `cache.redis_enabled` to confirm the wiring.
* **Async LLM rationale (opt-in)** — flip `RATIONALE_ASYNC=true` and signed-in callers get an instant template response while a Celery worker back-fills the Gemini rationale onto the persisted `analyze_history` row. Retries are bounded (3× with exponential backoff); terminal failures land in a dead-letter queue and bump `workers.failed_24h`. The frontend polls `/analyze/history` for the row and swaps in the upgraded text — no SSE/WebSocket required. Anonymous callers always take the synchronous path so they never see a degraded "template-only" response.
* **Admin observability** — `/admin` is gated behind `NEXT_PUBLIC_ADMIN_USER_ID` and renders rolling p50/p95/max latency + error rate per route. Two worker card grids: **last 24h** (`completed_24h`, `failed_24h`, Redis backend status, scraped from Redis counters bumped by the worker on success/failure) and **live** (`queue_depth`, `in_flight`, `dlq_size`, scraped from the RabbitMQ Management API every 5s). Either source unreachable degrades to zeros plus a status flag — `/metrics` itself never 5xxs.

### Engineering decisions worth calling out

A few non-obvious choices a reviewer might want context on. Each is a deliberate trade-off, not a default.

* **Fail-closed envelope contract on every helper.** `predict_tyre_wear`, `compute_lap_delta`, `strategy_analyzer`, `get_telemetry`, etc. all return populated `{..., fallback: True, fallback_reason: "..."}` instead of raising on FastF1 hiccups. Cost: every endpoint has to special-case nothing on the client. Benefit: the API never 5xxs because of a sparse practice session, and the UI can render an honest "data unavailable" state with the actual reason — no spinner-of-death.
* **`numpy.interp` for lap-vs-lap Δt instead of `fastf1.utils.delta_time`.** The library's helper is deprecated and known-inaccurate; we align both drivers' telemetry on a shared distance grid ourselves and rebase `SessionTime` to zero per-lap so the trace shows *gap accumulation along the lap*, not session-clock drift.
* **Build-time `NEXT_PUBLIC_*` injection, codified in compose.** Next inlines public env vars at `next build` time, not runtime. After hitting a prod-only "Sign in unavailable" failure that looked like an OAuth misconfig, we made compose fail-parse with `${VAR:?msg}` if any are missing, added a Makefile pre-flight grep, and put a `URL ✗ KEY ✗` diagnostic pill in the AuthButton so the next failure of this class is self-explaining.
* **Yarn 4 with `nodeLinker: node-modules`, not PnP.** Berry's PnP would shrink installs further but breaks Next 16 + Turbopack today. We picked the deterministic-install win and skipped the resolution-graph win — revisit when we move off Turbopack.
* **Async LLM rationale is opt-in, anonymous callers stay sync.** `RATIONALE_ASYNC=true` only kicks in for signed-in users — anonymous callers always get the synchronous path, never a degraded "template only" UX while waiting for a worker. Bounded retries (3× exponential backoff) + dead-letter queue + 24h success/failure counters surfaced on `/admin`.
* **BM25 + curated markdown for RAG, not a vector DB.** The knowledge corpus is 13 hand-written markdown files (FIA regulation snippets + F1 strategy concepts) under `backend/rag/corpus/`, indexed once at import via `rank-bm25`. Cost: no semantic similarity, no fuzzy paraphrase matching. Benefit: zero infra spend on the indie-hacker VPS, the corpus is auditable in version control, and a recruiter reading the repo can see exactly what the LLM is allowed to ground its rationale in. Revisit when corpus exceeds ~50 entries or when fuzzy retrieval becomes a real demand.
* **Hardened staging compose by default.** Redis with `requirepass` + renamed `CONFIG`/`FLUSHALL`/`FLUSHDB`, no host port mapping for Redis or RabbitMQ, `maxmemory + allkeys-lru` so a runaway cache key can't OOM-kill the VPS. Notes on each guardrail live inline in `docker-compose.staging.yml` so the reasoning survives the next refactor.

### Workflow loop

Every change in this repo goes through the same loop: GitHub issue → thin slice (one backend capability + one visible surface + one focused test) → conventional commit (`feat(backend): ...` / `fix(frontend): ...`) → PR against `develop` with **Summary / Why / What changed / Verification / Risks** sections. The CI job runs backend pytest, frontend `yarn lint`/`yarn build`, and `docker build` for both images on every PR. This is documented in `CLAUDE.md` and the `.claude/skills/` set, and is the reason recent merge history looks tight (4 PRs in one session for #182→#185 plus the auth-prod fix is normal cadence, not a sprint).

### Pre-baking the FastF1 cache

```bash
cd backend
FASTF1_PREBAKE_WRITE=true python3 -m scripts.prebake
```

The script iterates over a small `DEMO_SESSIONS` list (currently 2024 Monza R for VER/HAM/LEC) and writes one gzipped-JSON snapshot per helper call into `backend/data/prebake/`. Edit that list to bake additional sessions — each new entry costs one real FastF1 load (~5–30 s) but pays off on every subsequent restart. Snapshots are gitignored by default; commit them only if you want them shipped in the Docker image.

### LLM rationale eval harness

`backend/evals/cases/rationale_fixtures.py` ships a small set of pinned contexts that exercise the engineer-voice rationale (telemetry, strategy, citation-grounded, fallback). The eval is **opt-in** so CI never burns Gemini quota — both `RUN_LLM_EVAL=1` and `GEMINI_API_KEY` must be set:

```bash
cd backend
RUN_LLM_EVAL=1 python3 -m pytest tests/test_eval_rationale.py -v
```

Each fixture asserts that every `expected_substrings` entry appears in the generated text and no `forbidden_substrings` entry leaks through. Add a new case by appending to the fixtures file — the harness picks it up via parametrize, no harness change needed. Run before merging any prompt change in `core/llm.py`.

---

## Getting Started

Two supported paths: local dev (fastest feedback loop) and the staging-like Docker Compose stack (closer to what runs on the VPS).

### Prerequisites
* Python 3.11+
* Node.js 18+
* Docker + Docker Compose — only needed for Redis or the full staging stack. Either `docker compose` (v2 plugin) or `docker-compose` (v1 standalone) works; the Makefile auto-detects.

### 1. Clone & configure environment

```bash
git clone https://github.com/thdat-vu/f1-virtual-engineer.git
cd f1-virtual-engineer

cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

Fill in `backend/.env`:
- `GEMINI_API_KEY` — required for LLM rationale; without it the deterministic template fallback is used.
- `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` — optional, only needed for auth + per-user history.
- `REDIS_PASSWORD` — required if you bring up Redis. Generate with:
  ```bash
  openssl rand -base64 32 | tr -d '=+/' | cut -c1-32
  ```
- `REDIS_URL` — point at the Redis you bring up (`redis://:<password>@redis:6379/0` for compose, `redis://127.0.0.1:6379/0` for a host-installed Redis). Leave blank to skip the L2 cache and use in-process only.

### 2. Local dev (recommended for iterating)

```bash
make dev
```

That runs `scripts/dev.sh`, which:
- creates `.venv` + installs `backend/requirements.txt` if needed,
- runs `yarn install --immutable` in `frontend/` if `node_modules/` is missing (corepack pins yarn from `package.json#packageManager`),
- pre-flights ports 3000 + 8000 (a stale `next-server` or `uvicorn` from a previous session prints its PID + a ready-to-paste `kill` command instead of failing mid-startup),
- starts both processes and tears them down together on Ctrl-C.

URLs:
- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>
- Swagger / OpenAPI: <http://localhost:8000/docs>

### 3. Optional: bring up Redis for the L2 cache

Most code paths work fine without Redis (the L1 in-process TTLCache covers a single-process dev loop). Bring up Redis when you want to test multi-worker cache behavior, or before working on anything in `backend/core/redis_cache.py`.

```bash
make redis-up        # starts the redis container (uses backend/.env)
make redis-status    # confirm "(healthy)"
make redis-cli       # opens an authed redis-cli inside the container
make redis-down      # stops the stack
make redis-logs      # tail the redis container logs
```

The Makefile auto-detects whether you have `docker compose` (v2 plugin) or `docker-compose` (v1 standalone) and picks the right one. If `make redis-up` errors, the message tells you exactly what's missing (the file, the password, etc.).

> **Hardening note:** Redis is bound to the docker network only (no host port mapping), `requirepass` is mandatory, persistence is off, and admin commands like `CONFIG`/`FLUSHALL`/`FLUSHDB` are renamed. See [`docs/INFRA_HARDENING.md`](docs/INFRA_HARDENING.md) for the threat model and operator checklist.

### 4. Full staging-like stack with Docker Compose

For a reviewer-friendly run that mirrors production (api + frontend + redis + rabbitmq + celery worker + dlq-worker behind a single docker network):

```bash
make stack-up        # builds + starts every service
make stack-status    # confirms each container is healthy
make stack-logs      # follow combined logs (Ctrl-C to detach)
make worker-logs     # just the celery worker
make dlq-logs        # just the dead-letter consumer
make stack-down      # stops the stack
```

Both `REDIS_PASSWORD` and `RABBITMQ_PASSWORD` must be set in `backend/.env` first — the Makefile pre-flights and tells you exactly which one is missing instead of letting compose print its opaque interpolation error.

If you'd rather invoke compose directly:

```bash
# v2 plugin:
docker compose  --env-file backend/.env -f docker-compose.staging.yml up --build
# v1 standalone:
docker-compose --env-file backend/.env -f docker-compose.staging.yml up --build
```

Why the `--env-file backend/.env` flag matters: compose's auto-loaded `.env` lives at the **project root**, not at `backend/.env`. The `redis` service interpolates `${REDIS_PASSWORD:?...}` at compose-parse time (before any container starts), so without the flag you'll see `required variable REDIS_PASSWORD is missing a value`. The `env_file:` keys on `backend`/`frontend` only inject vars into those containers at runtime — they do nothing for top-level interpolation.

Expected URLs:
- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>

Stop the stack:

```bash
make stack-down
# or directly: docker compose --env-file backend/.env -f docker-compose.staging.yml down
```

Notes:
- For local dev outside Docker, `frontend/.env.local` keeps `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
- For the staging compose, browser requests go to `NEXT_PUBLIC_API_BASE_URL=/api` and Next.js rewrites `/api/*` to the internal backend URL via `BACKEND_INTERNAL_URL=http://backend:8000`.
- FastF1 cache is mounted through `./backend/data` so repeated runs are faster.

### Authentication (Supabase + Google)

The frontend now ships an optional Supabase Auth integration. Mission Control still works **anonymously** when the env vars are blank — the header just shows a disabled "Sign in unavailable" pill.

To enable real sign-in:

1. Create a Supabase project at <https://supabase.com>. From **Project Settings → API**, copy `URL` and `anon public` key into `frontend/.env.local`:
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
   ```
2. In **Authentication → Providers**, enable Google. Paste the OAuth client ID + secret from your Google Cloud Console (OAuth consent screen + Web Application credentials).
3. Add allowed redirect URLs in the Supabase auth settings:
   - `http://localhost:3000/auth/callback` (local dev)
   - your staging / production callback once that domain exists.
4. Restart `yarn dev`. The Mission Control header now shows "Sign in with Google"; signed-in users see their email + a "Sign out" button. The session is cookie-based and survives a refresh.

Signed-in users get `/analyze`, `/telemetry`, and radio history persisted server-side (Supabase Postgres + RLS), plus a Star button to save curated queries (driver, session, optional `vs <driver>` comparison). All four panels — Recent, Recently viewed, Radio log, Saved — live in the Mission Control right rail and replay the full analysis on click via the existing L1 + L2 cache.

### CI/CD recommendation for first user feedback

If your goal is to let the first real user open a browser URL and try the product quickly, use this path:

1. **GitHub Actions for CI**
   - run backend tests
   - run frontend lint/build
   - validate Docker images build successfully

2. **Deploy the built app to a simple platform**
   - easiest choices for indie-hacker speed: **Railway**, **Render**, **Fly.io**, or a small VPS with **Coolify**
   - use the new Dockerfiles or the compose setup as the deployment base

3. **Expose one public staging URL**
   - example: `https://staging.f1-virtual-engineer.app`
   - ask first users to try 2-3 suggested prompts from the landing page / mission-control flow

Important note: GitHub Actions alone does **not** host the app permanently. It is best used as CI, or as a trigger to deploy to a hosting platform that gives you the actual public URL.

Recommended fastest path after this issue lands:
- keep GitHub Actions as CI
- deploy frontend + backend on Railway or Render
- use the platform-generated URL first, add custom domain later

### API Docs (Swagger / OpenAPI)

When the backend is running, you can inspect and try the API contract from:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Recommended quick checks for reviewers:
- use `/telemetry` to verify the strict telemetry schema and fallback contract
- use `/analyze` to inspect telemetry-vs-strategy response envelopes for frontend integration; the response now includes a `rationale_source` field flagging whether the natural-language text came from Gemini or the deterministic template
- use `/radio/analyze` to classify a team-radio transcript into one of seven closed-set tags with severity + trigger phrase
- exceed `3/10s` on `/analyze` or `/radio/analyze` to see the structured `429` rate-limit envelope (`retry_after_seconds`, `Retry-After` header)

### Measuring response time

Every response now carries an `X-Process-Time` header (milliseconds, server-side wall-clock):

```bash
curl -s -o /dev/null -D - http://localhost:8000/events/2024 | grep -i x-process-time
# X-Process-Time: 1843.2
```

For an aggregated view across the last 50 samples per route:

```bash
curl -s http://localhost:8000/metrics | jq
# { "routes": { "GET /events/{year}": { "count": 12, "p50_ms": 1620.4, "p95_ms": 2810.1, "max_ms": 3104.7, "last_ms": 1843.2 }, ... } }
```

For end-to-end timing of a full curl call (network + server):

```bash
curl -s -o /dev/null -w 'total=%{time_total}s ttfb=%{time_starttransfer}s\n' \
  http://localhost:8000/events/2024
```

Browser side, open DevTools → Network and look at the waterfall: that's the only number the user actually feels. The header tells you whether slowness is server-side or network/CORS.

Set `METRICS_ENABLED=false` in `backend/.env` to disable both the header and the in-memory buffer (e.g. for stricter prod setups).

---

## Safety & Evaluation

To guarantee reliability in race-critical scenarios, the system implements:
* **Validation Gates:** All tool inputs are strictly validated using Pydantic schemas before execution.
* **Evaluation Suites:** Continuous testing against a "golden dataset" of historical race scenarios to measure accuracy and hallucination rates.
* **Observability:** Comprehensive logging of token usage, latency, and reasoning traces.

---

*Developed by ヴ・タイン・ダット - Showcasing the future of Agentic AI in high-performance sports.*
