import type { EventInfo } from "@/services/api";

const DAY_MS = 24 * 60 * 60 * 1000;
const WINDOW_DAYS = 3;

export interface ActiveRaceWeekend {
  name: string;
  location: string;
  raceDate: string;
}

function startOfUtcDay(date: Date): number {
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
}

function parseIsoDate(iso: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

export function getActiveRaceWeekend(
  events: EventInfo[],
  today: Date,
): ActiveRaceWeekend | null {
  const todayMs = startOfUtcDay(today);

  for (const event of events) {
    if (!event.event_date) continue;
    const raceMs = parseIsoDate(event.event_date);
    if (raceMs === null) continue;

    const windowStart = raceMs - WINDOW_DAYS * DAY_MS;
    if (todayMs >= windowStart && todayMs <= raceMs) {
      return {
        name: event.name,
        location: event.location,
        raceDate: event.event_date,
      };
    }
  }
  return null;
}
