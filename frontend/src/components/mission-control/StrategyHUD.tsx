"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { AnalyzeHistoryItem, AnalyzeResponse, SavedQueryItem, StrategyData, TelemetryHistoryItem } from "@/services/api";
import { TeamIcon } from "@/components/icons/TeamIcons";
import { RecentAnalyses } from "./RecentAnalyses";
import { RecentTelemetry } from "./RecentTelemetry";
import { RadioLog } from "./RadioLog";
import { ReferencesPanel } from "./ReferencesPanel";
import { SavedQueriesPanel } from "./SavedQueriesPanel";
import { TEAMS, type SessionId, type TeamId } from "./constants";

export function StrategyHUD({
  result, strat, isLoading, hasData, session, theme, rateLimitMessage,
  historyRefreshSignal, onSelectHistory,
  telemetryHistoryRefreshSignal, onSelectTelemetryHistory,
  radioHistoryRefreshSignal,
  savedQueries, onSavedQueriesChange, onSelectSaved,
}: {
  result: AnalyzeResponse | null;
  strat: StrategyData | null | undefined;
  isLoading: boolean;
  hasData: boolean;
  session: SessionId;
  theme: TeamId;
  rateLimitMessage?: string | null;
  historyRefreshSignal?: number;
  onSelectHistory?: (item: AnalyzeHistoryItem) => void;
  telemetryHistoryRefreshSignal?: number;
  onSelectTelemetryHistory?: (item: TelemetryHistoryItem) => void;
  radioHistoryRefreshSignal?: number;
  savedQueries: SavedQueryItem[];
  onSavedQueriesChange: (items: SavedQueryItem[]) => void;
  onSelectSaved?: (item: SavedQueryItem) => void;
}) {
  const activeTeam = TEAMS.find((t) => t.id === theme) ?? TEAMS[0];

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l border-border bg-surface">

      <div className="shrink-0 border-b border-border px-5 pt-5 pb-4">
        <div className="mb-1 flex items-center gap-2">
          <p className="label">Strategy HUD</p>
          <TeamIcon id={activeTeam.id} size={14} />
        </div>
        <div className="flex items-baseline justify-between">
          <span className="readout text-[length:var(--text-readout)] text-foreground-dim">
            {session} {"//"} {hasData && strat?.target_lap ? `PIT LAP ${strat.target_lap}` : "NO DATA"}
          </span>
          <span className="readout text-[length:var(--text-readout)] text-foreground-dim">
            {hasData && strat?.confidence_band ? strat.confidence_band.toUpperCase() : "—"}
          </span>
        </div>
      </div>

      {(() => {
        const status: "ok" | "warn" | "error" | "info" = rateLimitMessage
          ? "warn"
          : hasData && strat?.undercut_risk === "high"
            ? "error"
            : isLoading
              ? "info"
              : hasData
                ? "ok"
                : "info";
        const statusColor = `var(--status-${status})`;
        const statusBg = `var(--status-${status}-dim)`;
        const label = rateLimitMessage
          ? "⚠ RATE LIMITED"
          : hasData && strat?.undercut_risk === "high"
            ? "⚠ STRATEGY ALERT"
            : isLoading
              ? "ANALYZING"
              : hasData
                ? "ANALYSIS COMPLETE"
                : "SYSTEM STATUS";
        return (
          <div
            className="status-bar mx-4 mt-4 shrink-0 border p-4"
            data-status={status}
            style={{ borderColor: statusColor, background: statusBg }}
          >
            <p className="label mb-2" style={{ color: statusColor }}>{label}</p>
            <p className="readout text-[0.7rem] font-semibold uppercase leading-snug text-foreground">
              {rateLimitMessage
                ? rateLimitMessage
                : isLoading
                  ? "Fetching telemetry…"
                  : hasData
                    ? (result?.agent_response ?? "Analysis complete.")
                    : "Select year, grand prix, session and driver above."}
            </p>
          </div>
        );
      })()}

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-4">
        <p className="label mb-3">Tactical Rationale</p>
        <AnimatePresence mode="wait">
          <motion.ul key={hasData ? "data" : "idle"} className="space-y-2">
            {(hasData && strat?.rationale?.length
              ? strat.rationale
              : [
                  "Awaiting session selection.",
                  "Tyre degradation model ready.",
                  "Pace delta tracking idle.",
                  "Competitor windows standby.",
                ]
            ).map((line, i) => (
              <motion.li key={i}
                initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.07, duration: 0.3 }}
                className="readout flex gap-2 text-[length:var(--text-readout)] text-foreground-dim">
                <span className="text-accent">—</span>
                <span>{line}</span>
              </motion.li>
            ))}
          </motion.ul>
        </AnimatePresence>

        {hasData && strat?.recommended_pit_window_laps?.length === 2 && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="status-bar mb-4 mt-4 border p-3"
            data-status={strat.fallback ? "warn" : "ok"}
            style={{
              borderColor: strat.fallback ? "var(--status-warn)" : "var(--status-ok)",
              background: strat.fallback ? "var(--status-warn-dim)" : "var(--status-ok-dim)",
            }}
          >
            <p className="label mb-1" style={{ color: strat.fallback ? "var(--status-warn)" : "var(--status-ok)" }}>
              Pit Window {strat.fallback ? "· FALLBACK" : ""}
            </p>
            <p className="readout text-base font-bold text-accent">
              LAP {strat.recommended_pit_window_laps[0]} – {strat.recommended_pit_window_laps[1]}
            </p>
            {strat.fallback && (
              <p className="readout mt-1 text-[0.55rem]" style={{ color: "var(--status-warn)" }}>
                {strat.fallback_reason ?? "Estimate — live data unavailable"}
              </p>
            )}
          </motion.div>
        )}

        <ReferencesPanel items={result?.citations} />

        <RecentAnalyses refreshSignal={historyRefreshSignal} onSelect={onSelectHistory} />
        <RecentTelemetry
          refreshSignal={telemetryHistoryRefreshSignal}
          onSelect={onSelectTelemetryHistory}
        />
        <RadioLog refreshSignal={radioHistoryRefreshSignal} />
        <SavedQueriesPanel
          items={savedQueries}
          onItemsChange={onSavedQueriesChange}
          onSelect={onSelectSaved}
        />
      </div>
    </aside>
  );
}
