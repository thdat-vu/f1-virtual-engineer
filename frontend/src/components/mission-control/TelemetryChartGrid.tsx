"use client";

import type { AnalyzeResponse } from "@/services/api";
import { TelemetryChart } from "./TelemetryChart";
import { TimeAxis } from "./TimeAxis";

export function TelemetryChartGrid({
  tel, isLoading, hasData, animateKey, compareDriver, compareSpeedSeries,
}: {
  tel: AnalyzeResponse["telemetry_data"] | undefined;
  isLoading: boolean;
  hasData: boolean;
  animateKey: number;
  compareDriver: string;
  compareSpeedSeries: number[] | null;
}) {
  const lapDurationS = tel?.lap_duration_s ?? null;
  const sectorBoundariesS = tel?.sector_boundaries_s ?? [];
  // Sector lines on each chart: fractions of the X axis, derived from boundary seconds / lap duration.
  const sectorFractions =
    hasData && lapDurationS && lapDurationS > 0
      ? sectorBoundariesS.map((s) => s / lapDurationS).filter((f) => f > 0 && f < 1)
      : undefined;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-0 px-6 py-4">
      {(["Speed", "Throttle", "Brake"] as const).map((label, i) => {
        const ch = label === "Speed"    ? tel?.speed
                 : label === "Throttle" ? tel?.throttle
                 :                        tel?.brake;
        const overlay = label === "Speed" && compareSpeedSeries && compareDriver
          ? { compareSeries: compareSpeedSeries, compareLabel: compareDriver }
          : {};
        return (
          <div key={label} className={`min-h-0 flex-1 ${i > 0 ? "mt-3" : ""}`}>
            <TelemetryChart
              label={label}
              unit={label === "Speed" ? "KPH" : "%"}
              mode={label === "Speed" ? "line" : "area"}
              channelData={ch}
              isLoading={isLoading}
              hasData={hasData}
              animateKey={animateKey}
              sectorFractions={sectorFractions}
              {...overlay}
            />
          </div>
        );
      })}

      <TimeAxis
        lapDurationS={hasData ? lapDurationS : null}
        sectorBoundariesS={sectorBoundariesS}
        showYGutter={hasData}
      />
    </div>
  );
}
