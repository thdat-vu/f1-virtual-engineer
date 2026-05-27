import fs from "node:fs";
import path from "node:path";

export interface EvalStatus {
  passing: number;
  total: number;
  percent: number;
  lastUpdated: string;
}

// Last-known-good values. Used only if the JSON can't be reached at
// build time (e.g. a Docker context that didn't ship the backend
// directory). Keep this in sync with the JSON when bumping the gate
// — drift here just means stale numbers, not a broken build.
const FALLBACK: EvalStatus = {
  passing: 23,
  total: 25,
  percent: 92,
  lastUpdated: "2026-05-26",
};

// Reads the eval status JSON that the backend snapshot test gates
// CI on (`backend/evals/cases/strategy_pit_status.json`). Single
// source of truth — the landing page renders the same number CI
// enforces, so the "92%" claim can't drift.
//
// Server-only: imports `node:fs`, must never be pulled into a
// client component. The landing page is a Server Component, so
// the reader runs once per build and the parsed result is passed
// down as props.
export function readEvalStatus(): EvalStatus {
  // Two locations are checked — local dev runs from `frontend/`, so
  // the JSON sits one level up under `backend/...`. Docker builds
  // ship a copy inside the frontend image at public/data/ (see the
  // frontend Dockerfile COPY of the backend JSON). If neither
  // resolves, return baked-in defaults instead of breaking the
  // build.
  const candidates = [
    path.resolve(process.cwd(), "public/data/strategy_pit_status.json"),
    path.resolve(process.cwd(), "..", "backend/evals/cases/strategy_pit_status.json"),
  ];

  for (const filepath of candidates) {
    try {
      const raw = JSON.parse(fs.readFileSync(filepath, "utf8")) as {
        passing: number;
        total: number;
        last_updated: string;
      };
      const percent = raw.total > 0 ? Math.round((100 * raw.passing) / raw.total) : 0;
      return {
        passing: raw.passing,
        total: raw.total,
        percent,
        lastUpdated: raw.last_updated,
      };
    } catch {
      // try the next candidate
    }
  }

  return FALLBACK;
}
