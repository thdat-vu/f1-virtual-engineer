"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { analyzeTyre, type TyreAnalyzeResponse } from "@/services/api";
import type { SessionId } from "./constants";

// Story 02 surface: lap-time decay + compound + cliff-lap projection
// independent of the strategy graph. Renders nothing when no
// driver/event is selected — a card "Awaiting selection" duplicates
// the system-status bar above and adds noise.
//
// Why a separate fetch: tyre snapshot is cheap (cache-warm hit ~50ms)
// and answers a different question than /analyze. Keeping it
// independent means the card stays fresh even when the user is
// browsing without re-running strategy.

const COMPOUND_COLOR: Record<string, string> = {
  SOFT:   "var(--status-error)",
  MEDIUM: "var(--status-warn)",
  HARD:   "var(--foreground)",
  INTERMEDIATE: "var(--status-info)",
  WET:    "var(--status-info)",
};

function decayTone(decay: number): "ok" | "warn" | "error" {
  // Same thresholds the predict_tyre_wear heuristic uses.
  if (decay >= 0.45) return "error";
  if (decay >= 0.25) return "warn";
  return "ok";
}

export function TyreCard({
  year, event, session, driver,
}: {
  year: number;
  event: string;
  session: SessionId;
  driver: string;
}) {
  const [data, setData] = useState<TyreAnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!event || !driver) return;
    let cancelled = false;
    // Microtask defer satisfies the react-hooks/set-state-in-effect lint
    // rule the same way RecentAnalyses does — visible behaviour matches
    // a direct call.
    queueMicrotask(async () => {
      if (cancelled) return;
      setLoading(true);
      try {
        const res = await analyzeTyre({ year, event, session_type: session, driver });
        if (!cancelled) setData(res);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [year, event, session, driver]);

  if (!event || !driver) return null;

  const compound = data?.compound;
  const decay = data?.decay_seconds_per_lap ?? 0;
  const cliff = data?.cliff_lap_estimate;
  const stint = data?.stint_laps ?? 0;
  const isFallback = data?.fallback ?? false;
  const tone = decayTone(decay);
  const toneVar = `var(--status-${tone})`;
  const toneDim = `var(--status-${tone}-dim)`;

  return (
    <motion.section
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="status-bar mt-4 border p-3"
      data-status={isFallback ? "warn" : tone}
      style={{
        borderColor: isFallback ? "var(--status-warn)" : toneVar,
        background:  isFallback ? "var(--status-warn-dim)" : toneDim,
      }}
    >
      <div className="flex items-center justify-between">
        <p className="label" style={{ color: isFallback ? "var(--status-warn)" : toneVar }}>
          Tyre Intelligence
        </p>
        {compound && (
          <span
            className="readout border px-2 py-0.5 text-[0.55rem] font-bold uppercase tracking-[var(--track-wide)]"
            style={{
              borderColor: COMPOUND_COLOR[compound] ?? "var(--foreground-dim)",
              color:       COMPOUND_COLOR[compound] ?? "var(--foreground-dim)",
            }}
          >
            {compound}
          </span>
        )}
      </div>

      {loading && !data && (
        <p className="readout mt-2 text-[0.6rem] text-foreground-dim">
          Reading tyre decay…
        </p>
      )}

      {data && !isFallback && (
        <div className="mt-2 grid grid-cols-3 gap-2">
          <div>
            <p className="label text-[0.5rem] text-foreground-dim">Stint</p>
            <p className="readout text-sm font-bold text-foreground">{stint}L</p>
          </div>
          <div>
            <p className="label text-[0.5rem] text-foreground-dim">Decay</p>
            <p className="readout text-sm font-bold" style={{ color: toneVar }}>
              {decay.toFixed(2)}s/L
            </p>
          </div>
          <div>
            <p className="label text-[0.5rem] text-foreground-dim">Cliff</p>
            <p className="readout text-sm font-bold text-accent">
              {cliff != null ? `L${cliff}` : "—"}
            </p>
          </div>
        </div>
      )}

      {data && isFallback && (
        <p className="readout mt-2 text-[0.6rem]" style={{ color: "var(--status-warn)" }}>
          {data.fallback_reason ?? "Tyre data unavailable for this session."}
        </p>
      )}
    </motion.section>
  );
}
