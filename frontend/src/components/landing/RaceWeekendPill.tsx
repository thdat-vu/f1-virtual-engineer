"use client";

import { useEffect, useState } from "react";
import { getEventsByYear } from "@/services/api";
import {
  getActiveRaceWeekend,
  type ActiveRaceWeekend,
} from "@/lib/race-weekend";

export function RaceWeekendPill() {
  const [active, setActive] = useState<ActiveRaceWeekend | null>(null);

  useEffect(() => {
    let cancelled = false;
    const today = new Date();
    getEventsByYear(today.getUTCFullYear())
      .then((schedule) => {
        if (cancelled || schedule.status !== "success") return;
        setActive(getActiveRaceWeekend(schedule.events, today));
      })
      .catch(() => {
        // Silent fallback — pill is non-critical surface.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!active) return null;

  return (
    <div
      className="hidden items-center gap-2 border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 lg:inline-flex"
      role="status"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(74,222,128,0.9)]" />
      <span className="readout text-[0.55rem] uppercase tracking-[var(--track-wide)] text-emerald-400">
        This weekend
      </span>
      <span className="readout text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground">
        {active.name}
      </span>
    </div>
  );
}
