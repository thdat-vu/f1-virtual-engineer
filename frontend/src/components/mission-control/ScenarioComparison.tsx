"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  compareStrategies,
  type ScenarioOutcome,
  type ScenarioSpec,
} from "@/services/api";
import { ReferencesPanel } from "./ReferencesPanel";

// Slice B of the Strategy what-if comparison capability (#203). Renders
// two scenario outcomes side-by-side using the /strategy/compare endpoint
// from slice A (#202 / #204). Reuses the citation chip component from
// #198 inside each card so the explainability flow stays consistent.
//
// Preset shape: each preset is a pair of `ScenarioSpec` rows that differ
// only in `gap_override_seconds`. That's the one knob the helper actually
// honours today (see #202 implementation note); modelling target_lap or
// compound here would be a black-box claim.

type PresetId = "undercut_timing" | "aggressive_vs_steady";

interface Preset {
  id: PresetId;
  label: string;
  scenarios: ScenarioSpec[];
}

const PRESETS: Preset[] = [
  {
    id: "undercut_timing",
    label: "Undercut timing",
    scenarios: [
      { label: "Undercut now", gap_override_seconds: 0.8 },
      { label: "Hold +3 laps", gap_override_seconds: 2.5 },
    ],
  },
  {
    id: "aggressive_vs_steady",
    label: "Risk profile",
    scenarios: [
      { label: "Aggressive", gap_override_seconds: 1.2 },
      { label: "Steady hold", gap_override_seconds: 3.5 },
    ],
  },
];

export function ScenarioComparison({
  year,
  event,
  sessionType,
  driver,
  targetDriver,
}: {
  year: number;
  event: string;
  sessionType: string;
  driver: string;
  targetDriver: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [presetId, setPresetId] = useState<PresetId>("undercut_timing");

  // requestKey changes whenever any input that should re-fetch changes.
  // We compare it inside the effect's resolver before applying state, so
  // a slow earlier request can't overwrite a newer outcome. This pattern
  // also keeps `loading` derivable — no sync setState inside the effect
  // body (would otherwise trip react-hooks/set-state-in-effect, same rule
  // we worked around in LapDeltaChart).
  const requestKey = `${open ? 1 : 0}|${presetId}|${year}|${event}|${sessionType}|${driver}|${targetDriver ?? ""}`;
  const [result, setResult] = useState<{
    key: string;
    outcomes: ScenarioOutcome[] | null;
    error: string | null;
  }>({ key: "", outcomes: null, error: null });

  const loading = open && result.key !== requestKey;
  const outcomes = result.key === requestKey ? result.outcomes : null;
  const errorMessage = result.key === requestKey ? result.error : null;

  useEffect(() => {
    if (!open) return;
    const preset = PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    let cancelled = false;
    compareStrategies({
      year,
      event,
      session_type: sessionType,
      driver,
      target_driver: targetDriver,
      scenarios: preset.scenarios,
    })
      .then((res) => {
        if (cancelled) return;
        setResult({ key: requestKey, outcomes: res.scenarios, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setResult({
          key: requestKey,
          outcomes: null,
          error: err instanceof Error ? err.message : "Comparison failed",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [requestKey, open, presetId, year, event, sessionType, driver, targetDriver]);

  return (
    <section className="mt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between"
        aria-expanded={open}
      >
        <p className="label">Compare strategies</p>
        <span className="readout text-[0.6rem] text-foreground-dim">
          {open ? "−" : "+"}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="scenario-comparison"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div
              role="tablist"
              aria-label="Scenario presets"
              className="mt-3 flex gap-1 border border-border bg-surface-elevated p-1"
            >
              {PRESETS.map((preset) => {
                const active = preset.id === presetId;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setPresetId(preset.id)}
                    className={`readout flex-1 px-2 py-1 text-[0.6rem] uppercase tracking-wide transition-colors ${
                      active
                        ? "bg-accent-dim text-foreground"
                        : "text-foreground-dim hover:text-foreground"
                    }`}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>

            {errorMessage && (
              <p
                className="readout mt-3 border px-2 py-1.5 text-[0.6rem]"
                style={{
                  borderColor: "var(--status-error)",
                  background: "var(--status-error-dim)",
                  color: "var(--status-error)",
                }}
              >
                {errorMessage}
              </p>
            )}

            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {(loading || !outcomes
                ? [null, null]
                : outcomes
              ).map((outcome, i) => (
                <ScenarioCard
                  key={outcome ? `${presetId}-${i}-${outcome.label}` : `loading-${i}`}
                  outcome={outcome}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function ScenarioCard({ outcome }: { outcome: ScenarioOutcome | null }) {
  if (!outcome) {
    return (
      <div className="border border-border bg-surface-elevated/40 px-3 py-3">
        <div className="h-3 w-24 animate-pulse bg-border" />
        <div className="mt-3 h-6 w-16 animate-pulse bg-border" />
        <div className="mt-2 h-2 w-full animate-pulse bg-border" />
      </div>
    );
  }

  if (outcome.fallback) {
    return (
      <div
        className="border px-3 py-3"
        style={{
          borderColor: "var(--status-warn)",
          background: "var(--status-warn-dim)",
        }}
      >
        <p
          className="label text-[0.6rem]"
          style={{ color: "var(--status-warn)" }}
        >
          {outcome.label}
        </p>
        <p className="readout mt-2 text-[0.6rem] text-foreground-dim">
          {outcome.fallback_reason ?? "Live data unavailable for this scenario."}
        </p>
      </div>
    );
  }

  const gain = outcome.expected_gain_seconds;
  const gainColor =
    gain == null
      ? "var(--foreground-dim)"
      : gain >= 0
        ? "var(--status-ok)"
        : "var(--status-warn)";

  return (
    <div className="border border-border bg-surface-elevated/40 px-3 py-3">
      <p className="label text-[0.6rem]">{outcome.label}</p>

      <div className="mt-3 flex items-baseline gap-2">
        <span
          className="readout text-[1.1rem] font-bold leading-none"
          style={{ color: gainColor }}
          title="Net seconds ahead of rival after a ~3-lap reaction window"
        >
          {gain == null ? "—" : `${gain >= 0 ? "+" : ""}${gain.toFixed(1)}s`}
        </span>
        <span className="readout text-[0.55rem] uppercase tracking-wide text-foreground-faint">
          gain
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1">
        <span
          className="readout border px-1.5 py-0.5 text-[0.5rem] uppercase tracking-wide"
          style={{
            borderColor:
              outcome.confidence_band === "high"
                ? "var(--status-ok)"
                : outcome.confidence_band === "medium"
                  ? "var(--status-info)"
                  : "var(--status-warn)",
            color:
              outcome.confidence_band === "high"
                ? "var(--status-ok)"
                : outcome.confidence_band === "medium"
                  ? "var(--status-info)"
                  : "var(--status-warn)",
          }}
        >
          {outcome.confidence_band}
        </span>
        {outcome.current_gap_seconds != null && (
          <span className="readout text-[0.55rem] uppercase tracking-wide text-foreground-faint">
            gap {outcome.current_gap_seconds.toFixed(1)}s
          </span>
        )}
        {outcome.undercut_break_even_laps != null && (
          <span className="readout text-[0.55rem] uppercase tracking-wide text-foreground-faint">
            be {outcome.undercut_break_even_laps}L
          </span>
        )}
      </div>

      <ReferencesPanel items={outcome.citations} />
    </div>
  );
}
