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

interface Headline {
  tone: "ok" | "warn" | "error";
  text: string;
}

// "Cliff" in the backend is laps-from-stint-start, not race lap. So
// laps_to_cliff = cliff − stint_laps tells us how many laps of life
// the current set has left before the heuristic predicts pace drop.
//
// Issue #223: this app only loads finished sessions from FastF1 — there
// is no live mode. Imperative copy ("pit now") reads as a real-time
// instruction even though the race finished. When the roster contains
// actual pit-in laps we know stops already happened, so we drop the
// imperative and frame the card analytically.
function deriveHeadline(
  lapsToCliff: number | null,
  hasCliff: boolean,
  isHistorical: boolean,
): Headline {
  if (!hasCliff) {
    // Backend couldn't fit a slope (FastF1 sparse, sprint, etc).
    // Don't pretend with a 0 — say so plainly so the viewer trusts
    // the rest of the card instead of staring at a "0 laps" headline.
    return { tone: "warn", text: "Tyre slope unavailable" };
  }
  const n = lapsToCliff ?? 0;
  if (n <= 0) {
    return {
      tone: "error",
      text: isHistorical
        ? "Final stint past predicted cliff"
        : "Past the cliff · pit now",
    };
  }
  if (n <= 5) {
    return {
      tone: "warn",
      text: isHistorical
        ? `Stint ending within ${n} lap${n === 1 ? "" : "s"} of cliff`
        : `Cliff in ${n} lap${n === 1 ? "" : "s"} · pit window open`,
    };
  }
  return { tone: "ok", text: `~${n} laps before pace drops` };
}

function formatPitLaps(laps: number[]): string {
  return laps.map((n) => `L${n}`).join(", ");
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
  const confidence = data?.confidence_band ?? "low";
  const isFallback = data?.fallback ?? false;
  const actualPitLaps = data?.actual_pit_laps ?? [];
  // Issue #223: every session this app loads is finished — FastF1's
  // cache is what drives the card. The presence of recorded pit-in
  // laps is the strongest signal that we're looking at a completed
  // race rather than a live session, so use it to gate imperative copy.
  const isHistorical = actualPitLaps.length > 0;

  const hasCliff = cliff != null && cliff > 0;
  const lapsToCliff = hasCliff ? (cliff as number) - stint : null;
  const headline = deriveHeadline(lapsToCliff, hasCliff, isHistorical);

  // Progress fill: stint progress toward the cliff. Clamp to 100% so
  // "past the cliff" maxes out the bar visually instead of overflowing.
  const progressPct = hasCliff
    ? Math.min((stint / (cliff as number)) * 100, 100)
    : 0;

  const cardTone = isFallback ? "warn" : headline.tone;
  const toneVar = `var(--status-${cardTone})`;
  const toneDim = `var(--status-${cardTone}-dim)`;

  return (
    <motion.section
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="status-bar mt-4 border p-3"
      data-status={cardTone}
      style={{ borderColor: toneVar, background: toneDim }}
    >
      <div className="flex items-center justify-between">
        <p className="label" style={{ color: toneVar }}>
          Tyre Status
        </p>
        {compound && (
          <span
            className="readout border px-2 py-0.5 text-[0.55rem] font-bold uppercase tracking-[var(--track-wide)]"
            style={{
              borderColor: COMPOUND_COLOR[compound] ?? "var(--foreground-dim)",
              color:       COMPOUND_COLOR[compound] ?? "var(--foreground-dim)",
            }}
            title={`${compound} compound`}
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
        <>
          <p
            className="readout mt-2 text-[0.8rem] font-bold leading-snug"
            style={{ color: toneVar }}
          >
            {headline.text}
          </p>

          {/* Issue #185: snapshot lap context. The card always reflects
              the last lap in the loaded roster — without this line the
              viewer can read the headline as a call about whatever lap
              they're currently viewing on the chart.
              Issue #223: spell out "race finish" for historical sessions
              so "as of L58" doesn't read as a live snapshot. */}
          <p className="readout mt-1 text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground-faint">
            {data.last_lap_number != null
              ? isHistorical
                ? `as of L${data.last_lap_number} · race finish`
                : `as of L${data.last_lap_number}`
              : "as of last available lap"}
          </p>

          {/* Issue #223: ground the cliff heuristic in what actually
              happened. For a multi-stop race the user's first question
              is "what lap did they actually pit?" — answer it directly
              instead of leaving them to read "pit now" as live advice. */}
          {isHistorical && (
            <p className="readout mt-1 text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground-dim">
              actual stops: {formatPitLaps(actualPitLaps)}
            </p>
          )}

          {hasCliff && (
            <>
              <div
                className="mt-2 h-1.5 overflow-hidden border"
                style={{ borderColor: "var(--border)" }}
                role="progressbar"
                aria-valuenow={Math.round(progressPct)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Stint ${stint} of ~${cliff} laps`}
              >
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${progressPct}%` }}
                  transition={{ duration: 0.6, ease: [0.22, 0.61, 0.36, 1] }}
                  className="h-full"
                  style={{ background: toneVar }}
                />
              </div>
              <div className="mt-1 flex justify-between text-[0.5rem] uppercase tracking-[var(--track-wide)] text-foreground-dim">
                <span>L{stint} on tyres</span>
                <span>cliff ~L{cliff}</span>
              </div>
            </>
          )}

          {decay > 0 && (
            <p className="readout mt-2 text-[0.55rem] text-foreground-faint">
              Losing {decay.toFixed(2)}s every lap
              {confidence === "low" && (
                <span style={{ color: "var(--status-warn)" }}> · low confidence</span>
              )}
            </p>
          )}
        </>
      )}

      {data && isFallback && (
        <p className="readout mt-2 text-[0.6rem]" style={{ color: "var(--status-warn)" }}>
          {data.fallback_reason ?? "Tyre data unavailable for this session."}
        </p>
      )}
    </motion.section>
  );
}
