"use client";

import type { AnalyzeExecution, AnalyzeResponse, StrategyData } from "@/services/api";

function formatTrace(exec: AnalyzeExecution | null | undefined): string | null {
  if (!exec?.trace?.length) return null;
  const totals = new Map<string, { ms: number; error: boolean }>();
  for (const entry of exec.trace) {
    const prev = totals.get(entry.tool) ?? { ms: 0, error: false };
    prev.ms += entry.duration_ms;
    if (entry.status === "error") prev.error = true;
    totals.set(entry.tool, prev);
  }
  return Array.from(totals.entries())
    .map(([tool, { ms, error }]) => `${tool} ${Math.round(ms)}ms${error ? "!" : ""}`)
    .join(" · ");
}

export function MissionFooter({
  tel, strat, hasData, execution,
}: {
  tel: AnalyzeResponse["telemetry_data"] | undefined;
  strat: StrategyData | null | undefined;
  hasData: boolean;
  execution?: AnalyzeExecution | null;
}) {
  const traceSummary = formatTrace(execution);
  return (
    <footer className="flex h-9 shrink-0 items-center gap-5 overflow-hidden border-t border-border bg-surface px-6">
      {[
        { label: "RPM",  value: tel?.rpm    ? `${tel.rpm.avg.toFixed(0)} avg`  : "—" },
        { label: "Gear", value: tel?.gear   ? `${tel.gear.avg.toFixed(1)} avg` : "—" },
        { label: "Pts",  value: tel?.sample_points ? `${tel.sample_points} samples` : "—" },
      ].map(({ label, value }, i) => (
        <div key={label} className="flex items-center gap-2">
          {i > 0 && <div className="h-3 w-px bg-border" />}
          <span className="label">{label}</span>
          <span className="readout text-[length:var(--text-readout)] text-foreground">{value}</span>
        </div>
      ))}
      {traceSummary && (
        <div className="flex items-center gap-2">
          <div className="h-3 w-px bg-border" />
          <span className="label">TRACE</span>
          <span
            className="readout text-[length:var(--text-readout)] text-muted-foreground truncate max-w-[40ch]"
            title={traceSummary}
          >
            {traceSummary}
          </span>
        </div>
      )}
      <div className="ml-auto readout text-[length:var(--text-readout)] text-accent">
        {hasData && strat?.undercut_risk === "high" ? "HIGH UNDERCUT RISK" : hasData ? "ANALYSIS COMPLETE" : "AWAITING SESSION"}
      </div>
    </footer>
  );
}
