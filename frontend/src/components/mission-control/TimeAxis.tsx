"use client";

import { formatLapTime } from "./TelemetryChart";

const LEFT_GUTTER_PX = 48; // matches TelemetryChart's w-12 y-axis column

function pickTickSeconds(lapDurationS: number, sectorBoundariesS: number[]): number[] {
  // Always anchor 0 and lap end. Add sector boundaries as named ticks.
  // Add evenly spaced filler ticks (~5 total) so the axis isn't too sparse on long laps.
  const set = new Set<number>([0, lapDurationS]);
  for (const b of sectorBoundariesS) set.add(b);
  const fillerCount = lapDurationS > 75 ? 4 : lapDurationS > 30 ? 3 : 2;
  for (let i = 1; i < fillerCount; i++) set.add((lapDurationS * i) / fillerCount);
  return [...set].sort((a, b) => a - b);
}

export function TimeAxis({
  lapDurationS,
  sectorBoundariesS,
  showYGutter,
}: {
  lapDurationS: number | null | undefined;
  sectorBoundariesS: number[];
  showYGutter: boolean;
}) {
  if (!lapDurationS || lapDurationS <= 0) return null;
  const ticks = pickTickSeconds(lapDurationS, sectorBoundariesS);
  const sectorSet = new Set(sectorBoundariesS);

  return (
    <div className="mt-1 flex shrink-0 items-stretch">
      {showYGutter ? <div className="w-12 shrink-0 border-r border-transparent" /> : null}
      <div className="relative h-5 flex-1">
        {ticks.map((t, i) => {
          const pct = (t / lapDurationS) * 100;
          const label = t === 0 ? "0:00" : formatLapTime(t).replace(/(:\d{2})\.\d{3}/, "$1");
          const isSector = sectorSet.has(t);
          const isEnd = t === lapDurationS;
          return (
            <div
              key={`tick-${i}`}
              className="absolute top-0 flex flex-col items-center"
              style={{
                left: `${pct}%`,
                transform: i === 0 ? "translateX(0)" : isEnd ? "translateX(-100%)" : "translateX(-50%)",
              }}
            >
              <div
                className="h-1 w-px"
                style={{ background: isSector ? "var(--accent)" : "var(--foreground-faint)" }}
              />
              <span
                className="readout mt-0.5 text-[0.55rem] uppercase tracking-[var(--track-wide)] tabular-nums"
                style={{ color: isSector ? "var(--accent)" : "var(--foreground-faint)" }}
                title={isSector ? `Sector boundary @ ${label}` : `${label}`}
              >
                {isSector ? `S${sectorBoundariesS.indexOf(t) + 1} ${label}` : label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export { LEFT_GUTTER_PX };
