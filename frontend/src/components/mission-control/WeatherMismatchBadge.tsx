"use client";

import type { WeatherSummaryResponse } from "@/services/api";

// Cross-year weather mismatch badge (#242). Renders next to the
// cross-year delta chart when the two seasons had materially
// different track conditions, so a 5-second lap-delta isn't
// silently misread as "the new car found 5 seconds" when really
// 2023 was wet and 2024 was dry.
//
// Hides on any fallback summary — same silence-beats-half-info
// rule as WeatherPill (#235). Track temp threshold of 5°C chosen
// because tyre warm-up window shifts noticeably above that delta;
// smaller deltas don't warrant cluttering the chart.

const TRACK_TEMP_THRESHOLD_C = 5;

export function WeatherMismatchBadge({
  yearA, yearB, weatherA, weatherB,
}: {
  yearA: number;
  yearB: number;
  weatherA: WeatherSummaryResponse | null;
  weatherB: WeatherSummaryResponse | null;
}) {
  if (
    !weatherA || !weatherB ||
    weatherA.fallback || weatherB.fallback ||
    !weatherA.condition || !weatherB.condition
  ) return null;

  const conditionDiffers = weatherA.condition !== weatherB.condition;

  const trackTempDelta =
    weatherA.track_temp_c != null && weatherB.track_temp_c != null
      ? Math.abs(weatherA.track_temp_c - weatherB.track_temp_c)
      : null;
  const tempMismatch = trackTempDelta != null && trackTempDelta >= TRACK_TEMP_THRESHOLD_C;

  if (!conditionDiffers && !tempMismatch) return null;

  const earlier = yearA < yearB ? yearA : yearB;
  const later = yearA < yearB ? yearB : yearA;
  const earlierW = yearA < yearB ? weatherA : weatherB;
  const laterW = yearA < yearB ? weatherB : weatherA;

  const label = conditionDiffers
    ? `WX MISMATCH · ${earlier} ${earlierW.condition} vs ${later} ${laterW.condition}`
    : `WX Δ · ΔTrack ${Math.round(trackTempDelta!)}°C`;

  const tooltip =
    `${earlier}: ${earlierW.condition}${earlierW.track_temp_c != null ? ` · ${Math.round(earlierW.track_temp_c)}°C track` : ""}` +
    ` // ` +
    `${later}: ${laterW.condition}${laterW.track_temp_c != null ? ` · ${Math.round(laterW.track_temp_c)}°C track` : ""}`;

  return (
    <div className="mt-2 flex">
      <span
        className="readout shrink-0 border px-2 py-0.5 text-[0.55rem] font-bold uppercase tracking-[var(--track-wide)]"
        title={tooltip}
        style={{
          color: "var(--status-warn)",
          borderColor: "var(--status-warn)",
          background: "var(--status-warn-dim)",
        }}
      >
        {label}
      </span>
    </div>
  );
}
