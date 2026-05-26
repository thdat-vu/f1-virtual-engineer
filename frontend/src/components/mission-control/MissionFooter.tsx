"use client";

import type { AnalyzeExecution, AnalyzeResponse, StrategyData } from "@/services/api";

const GITHUB_URL = "https://github.com/thdat-vu/f1-virtual-engineer";

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
  const year = new Date().getFullYear();
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
      {/* Issue #231: solo-dev attribution surfaced inline because the
          h-screen mission-control layout can't take a second footer row.
          Landing uses the standard <Footer /> component. */}
      <div className="ml-auto flex items-center gap-3">
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="readout flex items-center gap-1.5 text-[length:var(--text-readout)] text-foreground-faint transition-colors hover:text-foreground"
          aria-label="View source on GitHub"
        >
          <svg viewBox="0 0 24 24" width={11} height={11} fill="currentColor" aria-hidden="true">
            <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.27-.01-1-.02-1.96-3.2.69-3.87-1.54-3.87-1.54-.52-1.32-1.27-1.67-1.27-1.67-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.69 1.24 3.35.95.1-.74.4-1.24.72-1.53-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.18-3.09-.12-.29-.51-1.46.11-3.05 0 0 .96-.31 3.15 1.18a10.96 10.96 0 0 1 5.74 0c2.19-1.49 3.15-1.18 3.15-1.18.62 1.59.23 2.76.11 3.05.74.8 1.18 1.83 1.18 3.09 0 4.42-2.69 5.39-5.25 5.68.41.35.78 1.04.78 2.1 0 1.52-.01 2.74-.01 3.11 0 .31.21.68.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z" />
          </svg>
          <span className="hidden sm:inline">© {year} Vu Thanh Dat</span>
          <span className="sm:hidden">© {year}</span>
        </a>
        <div className="h-3 w-px bg-border" />
        <div className="readout text-[length:var(--text-readout)] text-accent">
          {hasData && strat?.undercut_risk === "high" ? "HIGH UNDERCUT RISK" : hasData ? "ANALYSIS COMPLETE" : "AWAITING SESSION"}
        </div>
      </div>
    </footer>
  );
}
