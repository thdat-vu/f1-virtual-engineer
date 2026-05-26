"use client";

import type { WeatherSummaryResponse } from "@/services/api";

// Weather pill (#235). Compact readout next to the session breadcrumb in
// MissionHeader. Renders nothing while loading or when the API returned
// a fallback envelope — silence beats a half-populated pill that reads
// as "weather data missing" in copy.
//
// Condition tone:
//   DRY   → muted, the default state, no special framing.
//   MIXED → warn, drives the "should we switch compounds" question.
//   WET   → wet-tone (uses status-warn fill since we have no blue token),
//           same warn-class so it's still high-contrast against surface.

const CONDITION_TONE: Record<"DRY" | "MIXED" | "WET", string> = {
  DRY: "var(--foreground-dim)",
  MIXED: "var(--status-warn)",
  WET: "var(--status-warn)",
};

export function WeatherPill({ weather }: { weather: WeatherSummaryResponse | null }) {
  if (!weather || weather.fallback || !weather.condition) return null;

  const trackTemp = weather.track_temp_c != null ? `${Math.round(weather.track_temp_c)}°C track` : null;
  const rainfall =
    weather.condition !== "DRY" && weather.rainfall_fraction != null
      ? `${Math.round(weather.rainfall_fraction * 100)}% rain`
      : null;
  const trailing = trackTemp ?? rainfall;

  return (
    <span
      className="readout shrink-0 border border-border bg-surface-elevated px-2 py-0.5 text-[0.55rem] font-bold uppercase tracking-[var(--track-wide)]"
      title={`Air ${weather.air_temp_c ?? "—"}°C · Track ${weather.track_temp_c ?? "—"}°C · Wind ${weather.wind_speed_kmh ?? "—"} km/h`}
      style={{ color: CONDITION_TONE[weather.condition] }}
    >
      {weather.condition}
      {trailing ? ` · ${trailing}` : ""}
    </span>
  );
}
