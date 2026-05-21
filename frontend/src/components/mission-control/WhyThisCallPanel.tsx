"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { AnalyzeResponse, StrategyData } from "@/services/api";

// Story 04 surface: turn the recommendation from a confident paragraph
// into something a reviewer can audit. Source pill + assumptions + the
// existing rationale list + fallback reason live together so a user
// answering "why this call?" has every pillar in one collapsible.
//
// Why default-expanded: the rationale list used to be visible
// unconditionally on the HUD; collapsing it by default would silently
// hide the most-used surface. The toggle is for users who want to
// reclaim vertical room for history/saved panels.

export function WhyThisCallPanel({
  result,
  strat,
  hasData,
}: {
  result: AnalyzeResponse | null;
  strat: StrategyData | null | undefined;
  hasData: boolean;
}) {
  const [open, setOpen] = useState(true);

  const rationaleSource = result?.rationale_source ?? null;
  const assumptions = strat?.assumptions ?? [];
  const rationale = strat?.rationale ?? [];
  const fallback = strat?.fallback ?? false;
  const fallbackReason = strat?.fallback_reason ?? null;

  // Issue #183: render nothing when there's no strategy payload to
  // explain. The old idle copy ("Awaiting session selection · Tyre
  // degradation model ready · …") was a placeholder that survived
  // even after a successful telemetry-only analysis, which read as
  // "the rationale model didn't run." Better to hide the panel
  // entirely and give the vertical room back to the rest of the HUD.
  if (!hasData || rationale.length === 0) {
    return null;
  }

  // Source pill colors: LLM = info (blue), template = warn (amber) so a
  // reviewer can tell at a glance whether they're reading Gemini text or
  // the deterministic template — the latter is honest fallback, not
  // failure, but it changes how much weight the prose deserves.
  const sourcePill = rationaleSource === "llm"
    ? { label: "RATIONALE · LLM", color: "var(--status-info)", bg: "var(--status-info-dim)" }
    : rationaleSource === "template"
      ? { label: "RATIONALE · TEMPLATE", color: "var(--status-warn)", bg: "var(--status-warn-dim)" }
      : null;

  return (
    <section className="mt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between"
        aria-expanded={open}
      >
        <p className="label">Why this call?</p>
        <span className="readout text-[0.6rem] text-foreground-dim">
          {open ? "−" : "+"}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="why-body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            {sourcePill && (
              <span
                className="readout mt-3 inline-block border px-2 py-0.5 text-[0.55rem] uppercase tracking-[var(--track-wide)]"
                style={{ borderColor: sourcePill.color, color: sourcePill.color, background: sourcePill.bg }}
                aria-label={`Rationale source: ${rationaleSource}`}
              >
                {sourcePill.label}
              </span>
            )}

            <ul className="mt-3 space-y-2">
              {rationale.map((line, i) => (
                <motion.li
                  key={`${rationaleSource ?? "rationale"}-${i}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05, duration: 0.25 }}
                  className="readout flex gap-2 text-[length:var(--text-readout)] text-foreground-dim"
                >
                  <span className="text-accent">—</span>
                  <span>{line}</span>
                </motion.li>
              ))}
            </ul>

            {assumptions.length > 0 && (
              <div className="mt-4">
                <p className="label mb-2 text-[0.55rem]">Assumptions</p>
                <ul className="space-y-1.5">
                  {assumptions.map((line, i) => (
                    <li
                      key={i}
                      className="readout flex gap-2 text-[0.6rem] text-foreground-dim"
                    >
                      <span style={{ color: "var(--status-info)" }}>·</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {fallback && (
              <div
                className="status-bar mt-4 border p-2"
                data-status="warn"
                style={{ borderColor: "var(--status-warn)", background: "var(--status-warn-dim)" }}
              >
                <p
                  className="label mb-1 text-[0.55rem]"
                  style={{ color: "var(--status-warn)" }}
                >
                  Fallback in effect
                </p>
                <p className="readout text-[0.6rem] text-foreground">
                  {fallbackReason ?? "Live data unavailable — recommendation built from heuristic."}
                </p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
