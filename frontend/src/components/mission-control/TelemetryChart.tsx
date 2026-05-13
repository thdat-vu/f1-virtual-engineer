"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const CHART_VB_W = 1000;
const CHART_VB_H = 80;

export function formatLapTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return `${minutes}:${rest.toFixed(3).padStart(6, "0")}`;
}

function chartGeometry(series: number[], avg: number, compareSeries?: number[]) {
  if (series.length < 2) return null;
  const all = compareSeries && compareSeries.length > 1 ? [...series, ...compareSeries, avg] : [...series, avg];
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const span = hi - lo || 1;
  const padTop = CHART_VB_H * 0.075;
  const usable = CHART_VB_H * 0.85;
  const norm = (v: number) => CHART_VB_H - ((v - lo) / span) * usable - padTop;
  const stepX = CHART_VB_W / (series.length - 1);
  const points = series.map((v, i) => [i * stepX, norm(v)] as const);
  const linePath = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(" ");
  const areaPath = `M0 ${CHART_VB_H} ${points
    .map(([x, y]) => `L${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(" ")} L${CHART_VB_W} ${CHART_VB_H} Z`;

  let comparePath: string | null = null;
  if (compareSeries && compareSeries.length > 1) {
    const compareStep = CHART_VB_W / (compareSeries.length - 1);
    comparePath = compareSeries
      .map((v, i) => `${i === 0 ? "M" : "L"}${(i * compareStep).toFixed(1)} ${norm(v).toFixed(1)}`)
      .join(" ");
  }
  return { linePath, areaPath, avgY: norm(avg), norm, stepX, comparePath };
}

export function TelemetryChart({
  label, unit, channelData, isLoading, hasData, animateKey, mode = "line", compareSeries, compareLabel,
  sectorFractions,
}: {
  label: string; unit: string;
  channelData?: { min: number; max: number; avg: number; series?: number[] } | null;
  isLoading: boolean; hasData: boolean; animateKey: number;
  mode?: "line" | "area";
  compareSeries?: number[];
  compareLabel?: string;
  sectorFractions?: number[];
}) {
  const pathRef = useRef<SVGPathElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const geom = channelData?.series ? chartGeometry(channelData.series, channelData.avg, compareSeries) : null;
  const series = channelData?.series ?? [];
  const hoverPoint =
    hoverIdx !== null && geom && hoverIdx < series.length
      ? { value: series[hoverIdx], x: hoverIdx * geom.stepX, y: geom.norm(series[hoverIdx]) }
      : null;

  const handlePointer = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!series.length || !frameRef.current) return;
    const rect = frameRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    setHoverIdx(Math.round(ratio * (series.length - 1)));
  };

  useEffect(() => {
    if (!pathRef.current || !hasData) return;
    const len = pathRef.current.getTotalLength();
    pathRef.current.style.strokeDasharray = `${len}`;
    pathRef.current.style.strokeDashoffset = `${len}`;
    const anim = pathRef.current.animate(
      [{ strokeDashoffset: len }, { strokeDashoffset: 0 }],
      { duration: 900, easing: "cubic-bezier(0.22,1,0.36,1)", fill: "forwards" },
    );
    return () => anim.cancel();
    // geom is intentionally excluded from deps — it's rebuilt every render
    // (including on hover), which would reset the stroke-dash animation
    // mid-draw and leave the line's tail unpainted on wide viewports where
    // the cursor is usually over the chart.
  }, [hasData, animateKey]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mb-2 flex shrink-0 items-baseline justify-between">
        <span className="label">
          {label}
          {compareLabel ? (
            <span className="ml-2 text-foreground-faint">vs {compareLabel}</span>
          ) : null}
        </span>
        <AnimatePresence mode="wait">
          {hasData && channelData ? (
            <motion.div key="value" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-baseline gap-3">
              <span className="readout text-lg font-semibold text-foreground tabular-nums">
                {(hoverPoint?.value ?? channelData.avg).toFixed(0)}
              </span>
              <span className="label text-foreground-faint">
                {hoverPoint ? unit : `avg ${unit}`}
              </span>
            </motion.div>
          ) : (
            <motion.span key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="label text-foreground-faint">
              no data
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      <div className="relative flex min-h-0 flex-1 overflow-hidden border border-border bg-surface">
        {hasData && channelData ? (
          <div className="readout flex w-12 shrink-0 flex-col justify-between border-r border-border px-2 py-1.5 text-[0.55rem] text-foreground-faint">
            <span title={`max ${unit}`}>{channelData.max.toFixed(0)}</span>
            <span className="text-foreground-dim" title={`avg ${unit}`}>{channelData.avg.toFixed(0)}</span>
            <span title={`min ${unit}`}>{channelData.min.toFixed(0)}</span>
          </div>
        ) : null}

        <div
          ref={frameRef}
          className="relative min-h-0 flex-1"
          onPointerMove={handlePointer}
          onPointerLeave={() => setHoverIdx(null)}
        >
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <motion.div className="h-px w-10 bg-accent"
                animate={{ scaleX: [1, 2.5, 1], opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
              />
            </div>
          )}

          {!isLoading && !hasData && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="readout text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-faint">
                Select session above and run analysis
              </span>
            </div>
          )}

          {!isLoading && hasData && geom && (
            <svg className="h-full w-full" viewBox={`0 0 ${CHART_VB_W} ${CHART_VB_H}`} preserveAspectRatio="none">
              {sectorFractions?.map((f, i) => (
                <line
                  key={`sec-${i}`}
                  x1={f * CHART_VB_W} x2={f * CHART_VB_W} y1="0" y2={CHART_VB_H}
                  stroke="var(--foreground-faint)" strokeWidth="0.5" strokeDasharray="1 2"
                  opacity="0.55" vectorEffect="non-scaling-stroke"
                />
              ))}
              <line
                x1="0" x2={CHART_VB_W} y1={geom.avgY} y2={geom.avgY}
                stroke="var(--accent)" strokeWidth="0.4" strokeDasharray="3 3" opacity="0.35"
                vectorEffect="non-scaling-stroke"
              />
              {mode === "area" && (
                <path d={geom.areaPath} fill="var(--accent)" opacity="0.16" />
              )}
              {geom.comparePath && (
                <path
                  d={geom.comparePath}
                  fill="none"
                  stroke="var(--foreground-dim)"
                  strokeWidth="1.0"
                  strokeDasharray="2 2"
                  opacity="0.7"
                  vectorEffect="non-scaling-stroke"
                />
              )}
              <path
                ref={pathRef}
                d={geom.linePath}
                fill="none"
                stroke="var(--accent)"
                strokeWidth="1.4"
                vectorEffect="non-scaling-stroke"
              />
              {hoverPoint && (
                <>
                  <line
                    x1={hoverPoint.x} x2={hoverPoint.x} y1="0" y2={CHART_VB_H}
                    stroke="var(--foreground)" strokeWidth="0.5" opacity="0.4"
                    vectorEffect="non-scaling-stroke"
                  />
                  <circle
                    cx={hoverPoint.x}
                    cy={hoverPoint.y}
                    r="1.2"
                    fill="var(--foreground)"
                    vectorEffect="non-scaling-stroke"
                  />
                </>
              )}
            </svg>
          )}

          <div className="absolute inset-x-0 bottom-0 h-px bg-accent"
            style={{ opacity: hasData ? 0.2 : 0.06 }} />
        </div>
      </div>
    </div>
  );
}
