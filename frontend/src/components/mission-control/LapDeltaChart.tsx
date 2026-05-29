"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BoxBoxEmpty } from "@/components/ui/BoxBoxEmpty";
import { StartingGridLoader } from "@/components/ui/StartingGridLoader";

const CHART_VB_W = 1000;
const CHART_VB_H = 80;

// Symmetric Y range so the zero baseline is visually centered. Most
// laps land within ±1.5s; we clamp the floor so a flat lap doesn't
// blow up vertical noise.
const MIN_Y_RANGE = 0.4;

function geometry(distances: number[], deltas: number[]) {
  if (distances.length < 2 || deltas.length < 2) return null;
  const peak = Math.max(MIN_Y_RANGE, ...deltas.map((v) => Math.abs(v)));
  const padTop = CHART_VB_H * 0.075;
  const usable = CHART_VB_H * 0.85;
  const yFor = (v: number) => CHART_VB_H - ((v + peak) / (2 * peak)) * usable - padTop;

  const maxDist = distances[distances.length - 1] || 1;
  const xFor = (d: number) => (d / maxDist) * CHART_VB_W;

  const points = distances.map((d, i) => [xFor(d), yFor(deltas[i])] as const);
  const linePath = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(" ");

  // Two area fills, one above and one below the zero baseline. We
  // clip each fill at zero so the colours actually mean "ahead" vs
  // "behind" rather than a single ramp from min to max.
  const zeroY = yFor(0);
  const aboveArea = `M0 ${zeroY} ${points
    .map(([x, y]) => `L${x.toFixed(1)} ${Math.min(y, zeroY).toFixed(1)}`)
    .join(" ")} L${CHART_VB_W} ${zeroY} Z`;
  const belowArea = `M0 ${zeroY} ${points
    .map(([x, y]) => `L${x.toFixed(1)} ${Math.max(y, zeroY).toFixed(1)}`)
    .join(" ")} L${CHART_VB_W} ${zeroY} Z`;

  return { linePath, aboveArea, belowArea, zeroY, peak };
}

export function LapDeltaChart({
  distances, deltas, referenceDriver, compareDriver, isLoading, hasData, animateKey,
  fallback, fallbackReason,
}: {
  distances: number[];
  deltas: number[];
  referenceDriver: string;
  compareDriver: string;
  isLoading: boolean;
  hasData: boolean;
  animateKey: number;
  fallback: boolean;
  fallbackReason?: string | null;
}) {
  const pathRef = useRef<SVGPathElement>(null);
  const geom = hasData ? geometry(distances, deltas) : null;
  const finalDelta = deltas.length > 0 ? deltas[deltas.length - 1] : null;

  useEffect(() => {
    if (!pathRef.current || !hasData || !geom) return;
    const pathEl = pathRef.current;
    pathEl.style.strokeDasharray = "1";
    pathEl.style.strokeDashoffset = "1";
    const anim = pathEl.animate(
      [{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }],
      { duration: 900, easing: "cubic-bezier(0.22,1,0.36,1)", fill: "forwards" },
    );
    const bake = () => {
      pathEl.style.strokeDasharray = "none";
      pathEl.style.strokeDashoffset = "0";
    };
    anim.addEventListener("finish", bake);
    return () => {
      anim.removeEventListener("finish", bake);
      anim.cancel();
      bake();
    };
  }, [hasData, animateKey, geom]);

  const finalDeltaLabel = finalDelta !== null
    ? `${finalDelta >= 0 ? "+" : ""}${finalDelta.toFixed(2)}s`
    : "—";
  const finalDeltaTone = finalDelta === null
    ? "var(--foreground-faint)"
    : finalDelta > 0
      ? "var(--status-warn)"  // compare behind ⇒ reference ahead
      : "var(--accent)";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mb-2 flex shrink-0 items-baseline justify-between">
        <span className="label">
          Δt
          {compareDriver && referenceDriver ? (
            <span className="ml-2 text-foreground-faint">
              {compareDriver} vs {referenceDriver}
            </span>
          ) : null}
        </span>
        <AnimatePresence mode="wait">
          {hasData && geom ? (
            <motion.div key="value" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-baseline gap-3">
              <span
                className="readout text-lg font-semibold tabular-nums"
                style={{ color: finalDeltaTone }}
              >
                {finalDeltaLabel}
              </span>
              <span className="label text-foreground-faint">end of lap</span>
            </motion.div>
          ) : (
            <motion.span key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="label text-foreground-faint">
              {fallback && fallbackReason ? "unavailable" : "no data"}
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      <div className="relative flex min-h-0 flex-1 overflow-hidden border border-border bg-surface">
        {hasData && geom ? (
          <div className="readout flex w-12 shrink-0 flex-col justify-between border-r border-border px-2 py-1.5 text-[0.55rem] text-foreground-faint">
            <span title="compare behind">+{geom.peak.toFixed(2)}s</span>
            <span className="text-foreground-dim" title="even">0.00s</span>
            <span title="compare ahead">−{geom.peak.toFixed(2)}s</span>
          </div>
        ) : null}

        <div className="relative min-h-0 flex-1">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <StartingGridLoader />
            </div>
          )}

          {!isLoading && !hasData && (
            <div className="absolute inset-0 flex items-center justify-center">
              <BoxBoxEmpty
                message={
                  fallback && fallbackReason
                    ? fallbackReason
                    : compareDriver
                      ? "Computing Δt"
                      : "Pick a compare driver"
                }
                hint={
                  fallback && fallbackReason
                    ? undefined
                    : compareDriver
                      ? undefined
                      : "to see lap-by-lap delta"
                }
              />
            </div>
          )}

          {!isLoading && hasData && geom && (
            <svg className="h-full w-full" viewBox={`0 0 ${CHART_VB_W} ${CHART_VB_H}`} preserveAspectRatio="none">
              {/* compare-behind region — warn tone (reference ahead) */}
              <path d={geom.belowArea} fill="var(--status-warn)" opacity="0.18" />
              {/* compare-ahead region — accent tone */}
              <path d={geom.aboveArea} fill="var(--accent)" opacity="0.18" />
              <line
                x1="0" x2={CHART_VB_W} y1={geom.zeroY} y2={geom.zeroY}
                stroke="var(--foreground-dim)" strokeWidth="0.5" strokeDasharray="3 3" opacity="0.6"
                vectorEffect="non-scaling-stroke"
              />
              <path
                ref={pathRef}
                d={geom.linePath}
                pathLength="1"
                fill="none"
                stroke="var(--foreground)"
                strokeWidth="1.4"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          )}

          <div className="absolute inset-x-0 bottom-0 h-px bg-accent"
            style={{ opacity: hasData ? 0.2 : 0.06 }} />
        </div>
      </div>
    </div>
  );
}
