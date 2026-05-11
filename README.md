# Apex-Intelligence: Virtual Engineer F1

[![CI](https://github.com/thdat-vu/f1-virtual-engineer/actions/workflows/ci.yml/badge.svg)](https://github.com/thdat-vu/f1-virtual-engineer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**Apex-Intelligence** is an end-to-end Agentic AI system designed to act as a virtual Formula 1 race engineer. This system leverages advanced Large Language Models to process real-time telemetry, retrieve historical race data, and provide strategic recommendations such as pit-stop timing (undercut/overcut) and tire degradation analysis.

---

## System Architecture

The project follows a robust, production-ready agentic workflow separating business logic from AI execution:

* **Frontend (Next.js Dashboard):** A real-time interface displaying telemetry charts and the agent's reasoning traces.
* **Backend API (FastAPI):** Chosen because FastAPI is fast to develop, supports async, has strong typing via Pydantic, and generates OpenAPI docs[cite: 303].
* **Agent Orchestrator (LangGraph):** Manages multi-agent coordination. It models agent behavior as a graph with nodes (steps) and edges (transitions), which is easier to reason about than implicit loops[cite: 88].
* **Data Connectors:** Custom Python wrappers for the `FastF1` library to extract speed, throttle, brake, and tire data.
* **RAG System:** A vector database (Supabase/ChromaDB) storing FIA regulations and historical race strategies.

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
* **`docker-compose.yml`**: Full system containerization.

---

## Tech Stack

* **Language:** Python 3.11+ (Backend) & TypeScript (Frontend)
* **AI Orchestration:** LangGraph, LangChain
* **API Framework:** FastAPI, Pydantic
* **Telemetry Data:** FastF1
* **Vector Database:** Supabase / PostgreSQL
* **Caching:** `cachetools` TTLCache (L1, in-process) + optional Redis (L2, shared across workers)
* **Deployment:** Docker, Docker Compose

---

## Core Agent Capabilities

The Virtual Engineer is equipped with strict tool-use policies and capabilities. Shipped capabilities are exposed as endpoints today; pending ones are tracked in [open issues](https://github.com/thdat-vu/f1-virtual-engineer/issues).

| Capability | Status | Endpoint |
| --- | --- | --- |
| `get_telemetry` — speed/gear/RPM/throttle/brake summaries with fallback metadata | ✅ Shipped | `GET /telemetry`, `GET /laps/{...}` |
| `strategy_analyzer` — pit-window recommendations with undercut/overcut risk and confidence band | ✅ Shipped | `POST /analyze` (strategy intent) |
| `race_engineer_rationale` — Gemini Flash-generated natural-language summary, with deterministic template fallback when the LLM is unavailable | ✅ Shipped | `POST /analyze` (`rationale_source: "llm" \| "template"`) |
| `radio_interpreter` — closed-set classification of team-radio transcripts (tyre/brake/engine/traffic/weather/strategy/none) with severity + trigger phrase | ✅ Shipped | `POST /radio/analyze` |
| `predict_tyre_wear` — standalone tyre-degradation forecast | 🟡 Partial (covered inside `strategy_analyzer`) | — |
| `knowledge_retriever` — RAG over FIA regulations + historical incidents | ⏳ Planned | tracked in `#25`, `#26` |
| Google sign-in (Supabase Auth foundation) | ✅ Shipped | `/auth/callback` (frontend) |
| Per-user `/analyze` history — opt-in persistence by session, list endpoint, Mission Control "Recent" panel | ✅ Shipped | `POST /analyze` (writes when JWT present), `GET /analyze/history` |
| Per-user `/telemetry` history — opt-in persistence by session, list endpoint, Mission Control "Recently viewed" panel | ✅ Shipped | `POST /telemetry` (writes when JWT present), `GET /telemetry/history` |
| Per-user radio history + saved/favorited queries | ⏳ Planned | tracked in `#95` (radio) + follow-up issue for saved queries |

### Reliability features already in production

* **Rate limiting** — `slowapi` token-bucket on the LLM and telemetry routes; structured 429 envelope with `retry_after_seconds` and a `Retry-After` header.
* **Fail-closed LLM path** — every Gemini call is wrapped so a missing key, timeout, or malformed response degrades to a deterministic fallback rather than a 500.
* **In-memory response cache (60 s TTL)** — repeated identical LLM calls are served from a SHA-256-keyed cache, namespaced by call type.
* **FastF1 result cache + threadpool offload** — schedule/roster/lap-list responses are cached in-process for 24 h, telemetry summaries + tyre features for 1 h. Fallback/empty results are *not* cached, so a transient FastF1 hiccup never sticks. Helper calls now run on the FastAPI threadpool (`asyncio.to_thread`) so a slow FastF1 fetch no longer blocks the event loop for concurrent requests.
* **Pre-baked cache warmup** — `backend/scripts/prebake.py` records helper outputs to `backend/data/prebake/<helper>/*.json.gz`. On startup the FastAPI lifespan hook seeds the in-process TTLCaches from those snapshots, so the first user after a restart hits warm-cache latency for the demo session set instead of paying the multi-second FastF1 cold load.
* **Optional Redis L2 cache** — set `REDIS_URL` (e.g. `redis://localhost:6379/0`) and the FastF1 helpers gain a second tier: L1 in-process → L2 Redis → compute. Multi-worker / multi-pod deployments share the same warmed-up state instead of each process refilling its own cache. A Redis outage degrades silently to "L1 only" — the API never 5xxs because of cache infrastructure. Inspect `GET /metrics` → `cache.redis_enabled` to confirm the wiring.

### Pre-baking the FastF1 cache

```bash
cd backend
FASTF1_PREBAKE_WRITE=true python3 -m scripts.prebake
```

The script iterates over a small `DEMO_SESSIONS` list (currently 2024 Monza R for VER/HAM/LEC) and writes one gzipped-JSON snapshot per helper call into `backend/data/prebake/`. Edit that list to bake additional sessions — each new entry costs one real FastF1 load (~5–30 s) but pays off on every subsequent restart. Snapshots are gitignored by default; commit them only if you want them shipped in the Docker image.

---

## Getting Started

The system is containerized for seamless local development, optimized for Apple Silicon (M-series) and cloud deployments.

### Prerequisites
* Docker & Docker Compose
* Python 3.11+
* Node.js 18+

### Installation Steps

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/f1-virtual-engineer.git](https://github.com/your-username/f1-virtual-engineer.git)
    cd f1-virtual-engineer
    ```

2.  **Environment Setup:**
    * Backend: `cp backend/.env.example backend/.env`
    * Frontend: `cp frontend/.env.local.example frontend/.env.local`
    * Add your required API keys (e.g., Gemini API, Supabase) and backend URL for frontend API calls.

3.  **Run with Docker:**
    ```bash
    docker-compose up --build
    ```
    * *The Backend will be available at `http://localhost:8000`*
    * *The Frontend will be available at `http://localhost:3000`*

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
4. Restart `npm run dev`. The Mission Control header now shows "Sign in with Google"; signed-in users see their email + a "Sign out" button. The session is cookie-based and survives a refresh.

Signed-in users now also get `/analyze` history persisted server-side (Supabase Postgres + RLS) and surfaced in the Mission Control "Recent" panel. Per-user telemetry + radio history are still tracked under `#94`–`#95`.

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
   - example: `https://staging.apex-intelligence.app`
   - ask first users to try 2-3 suggested prompts from the landing page / mission-control flow

Important note: GitHub Actions alone does **not** host the app permanently. It is best used as CI, or as a trigger to deploy to a hosting platform that gives you the actual public URL.

Recommended fastest path after this issue lands:
- keep GitHub Actions as CI
- deploy frontend + backend on Railway or Render
- use the platform-generated URL first, add custom domain later

### Staging-like Docker Compose

For a first-publish / reviewer-friendly run path, the repo now includes a staging-like compose file:

```bash
docker compose -f docker-compose.staging.yml up --build
```

Expected URLs after startup:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

Before first run, make sure these files exist:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

Notes:
- For plain local dev outside Docker, `frontend/.env.local` can keep `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
- For staging-like Docker Compose, browser requests should go to `NEXT_PUBLIC_API_BASE_URL=/api`.
- Inside Docker Compose, Next.js rewrites `/api/*` to the internal backend URL from `BACKEND_INTERNAL_URL=http://backend:8000`.
- FastF1 cache is mounted through `./backend/data` so repeated runs are faster.

To stop the stack:

```bash
docker compose -f docker-compose.staging.yml down
```

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