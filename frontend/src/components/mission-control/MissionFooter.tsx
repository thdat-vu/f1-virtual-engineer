"use client";

import type { AnalyzeResponse, StrategyData } from "@/services/api";

export function MissionFooter({
  tel, strat, hasData,
}: {
  tel: AnalyzeResponse["telemetry_data"] | undefined;
  strat: StrategyData | null | undefined;
  hasData: boolean;
}) {
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
      <div className="ml-auto readout text-[length:var(--text-readout)] text-accent">
        {hasData && strat?.undercut_risk === "high" ? "HIGH UNDERCUT RISK" : hasData ? "ANALYSIS COMPLETE" : "AWAITING SESSION"}
      </div>
    </footer>
  );
}
