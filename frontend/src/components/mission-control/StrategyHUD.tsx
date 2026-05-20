"use client";

import { motion } from "framer-motion";
import type { AnalyzeHistoryItem, AnalyzeResponse, SavedQueryItem, StrategyData, TelemetryHistoryItem } from "@/services/api";
import { TeamIcon } from "@/components/icons/TeamIcons";
import { useSupabase } from "@/components/auth/SupabaseProvider";
import { useRationaleUpgrade } from "@/hooks/useRationaleUpgrade";
import { RecentAnalyses } from "./RecentAnalyses";
import { RecentTelemetry } from "./RecentTelemetry";
import { RadioLog } from "./RadioLog";
import { ReferencesPanel } from "./ReferencesPanel";
import { SavedQueriesPanel } from "./SavedQueriesPanel";
import { TyreCard } from "./TyreCard";
import { WhyThisCallPanel } from "./WhyThisCallPanel";
import { TEAMS, type SessionId, type TeamId } from "./constants";

export function StrategyHUD({
  result, strat, isLoading, hasData, session, theme, rateLimitMessage,
  retryState = "idle", onRetryClick,
  year, eventName, driver,
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
  retryState?: "idle" | "retrying" | "failed";
  onRetryClick?: () => void;
  year: number;
  eventName: string;
  driver: string;
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

  // Async rationale upgrade (#139 PR4): when /analyze returns
  // rationale_source='template' plus an analyze_history_id, the worker
  // is back-filling the LLM rationale onto that row. Poll /analyze/history
  // until the row flips to 'llm' and swap the displayed text.
  const supa = useSupabase();
  const accessToken = supa.session?.access_token ?? null;
  const upgrade = useRationaleUpgrade({
    rowId: result?.analyze_history_id ?? null,
    initialSource: result?.rationale_source ?? null,
    accessToken,
  });
  const displayedAgentResponse =
    upgrade.status === "upgraded" && upgrade.rationaleText
      ? upgrade.rationaleText
      : (result?.agent_response ?? "Analysis complete.");

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
                    ? displayedAgentResponse
                    : "Select year, grand prix, session and driver above."}
            </p>
            {upgrade.status === "pending" && (
              <p
                className="readout mt-2 inline-flex items-center gap-1.5 text-[0.6rem] uppercase tracking-[var(--track-wide)]"
                style={{ color: "var(--status-info)" }}
                aria-live="polite"
              >
                <motion.span
                  className="inline-block"
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1.4, ease: "linear" }}
                >
                  ↻
                </motion.span>
                Upgrading rationale…
              </p>
            )}
            {upgrade.status === "upgraded" && (
              <p
                className="readout mt-2 text-[0.6rem] uppercase tracking-[var(--track-wide)]"
                style={{ color: "var(--status-ok)" }}
              >
                ✓ Rationale upgraded
              </p>
            )}
            {retryState === "retrying" && (
              <p
                className="readout mt-2 inline-flex items-center gap-1.5 text-[0.6rem] uppercase tracking-[var(--track-wide)]"
                style={{ color: "var(--status-warn)" }}
                aria-live="polite"
              >
                <motion.span
                  className="inline-block"
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1.4, ease: "linear" }}
                >
                  ↻
                </motion.span>
                Network blip — retrying…
              </p>
            )}
            {retryState === "failed" && (
              <div className="mt-2 flex items-center justify-between gap-2">
                <p
                  className="readout text-[0.6rem] uppercase tracking-[var(--track-wide)]"
                  style={{ color: "var(--status-error)" }}
                  aria-live="polite"
                >
                  Network unstable — try again
                </p>
                {onRetryClick && (
                  <button
                    type="button"
                    onClick={onRetryClick}
                    className="readout border px-2 py-0.5 text-[0.55rem] uppercase tracking-[var(--track-wide)] transition-colors hover:bg-[var(--status-error-dim)]"
                    style={{ borderColor: "var(--status-error)", color: "var(--status-error)" }}
                  >
                    Try again
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })()}

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-4">
        <WhyThisCallPanel result={result} strat={strat} hasData={hasData} />

        <TyreCard year={year} event={eventName} session={session} driver={driver} />

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
            {strat.current_gap_seconds != null && (
              <p
                className="readout mt-1 text-[0.6rem] uppercase tracking-[var(--track-wide)] text-foreground-dim"
                title={
                  strat.gap_source === "fastf1"
                    ? `Sampled lap ${strat.gap_sampled_at_lap ?? "—"} from FastF1`
                    : strat.gap_source === "fallback"
                      ? "Live gap unavailable — using 1.2s assumption"
                      : "Explicit override"
                }
              >
                {strat.competitor_ahead
                  ? `vs ${strat.competitor_ahead}${
                      strat.competitor_position_relative === "behind" ? " ↓" : ""
                    } · `
                  : "Gap · "}
                <span className="text-foreground">{strat.current_gap_seconds.toFixed(1)}s</span>
                {" → undercut "}
                <span
                  className="font-bold"
                  style={{
                    color:
                      strat.undercut_risk === "high"
                        ? "var(--status-error)"
                        : strat.undercut_risk === "medium"
                          ? "var(--status-warn)"
                          : "var(--status-ok)",
                  }}
                >
                  {strat.undercut_risk}
                </span>
                {strat.gap_source === "fallback" && (
                  <span style={{ color: "var(--status-warn)" }}> · est.</span>
                )}
              </p>
            )}
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
