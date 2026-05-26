// F1 season list derived at render time so the dropdown auto-includes
// new seasons without a manual edit (#225).
//
// FastF1 has gappy data before 2018 (sectors / lap_time fields), so the
// floor is held there even though the upstream library accepts older
// years. The backend pydantic schemas independently validate
// `ge=2018, le=2100`, so any UI past that floor would be rejected.
//
// `now` is injected so consumers can pin to a fixed clock in tests
// when a test runner is wired up later — frontend doesn't have one yet.

const F1_DATA_FLOOR_YEAR = 2018;

export function availableSeasons(now: Date = new Date()): number[] {
  const current = now.getFullYear();
  if (current < F1_DATA_FLOOR_YEAR) {
    // Defensive: a clock skew shouldn't blank the dropdown.
    return [F1_DATA_FLOOR_YEAR];
  }
  const length = current - F1_DATA_FLOOR_YEAR + 1;
  return Array.from({ length }, (_, i) => current - i);
}

export function defaultSeason(now: Date = new Date()): number {
  return Math.max(now.getFullYear(), F1_DATA_FLOOR_YEAR);
}
