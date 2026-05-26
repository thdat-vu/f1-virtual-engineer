import fs from "node:fs";
import path from "node:path";

export interface EvalStatus {
  passing: number;
  total: number;
  percent: number;
  lastUpdated: string;
}

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
  const filepath = path.resolve(
    process.cwd(),
    "..",
    "backend/evals/cases/strategy_pit_status.json",
  );
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
}
