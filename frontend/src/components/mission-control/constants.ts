export const TEAMS = [
  { id: "ferrari",     color: "#DC0000", label: "Ferrari" },
  { id: "redbull",     color: "#1E2A78", label: "Red Bull" },
  { id: "mercedes",    color: "#00D2BE", label: "Mercedes" },
  { id: "mclaren",     color: "#FF8700", label: "McLaren" },
  { id: "alpine",      color: "#1F5EFF", label: "Alpine" },
  { id: "astonmartin", color: "#006F62", label: "Aston Martin" },
  { id: "williams",    color: "#005AFF", label: "Williams" },
  { id: "haas",        color: "#B6BABD", label: "Haas" },
  { id: "rb",          color: "#6692FF", label: "Racing Bulls" },
  { id: "audi",        color: "#C8C8C8", label: "Revolut Audi" },
  { id: "cadillac",    color: "#D4AF37", label: "Cadillac" },
] as const;
export type TeamId = (typeof TEAMS)[number]["id"];

// Year list now derives from the system clock (#225) — see lib/f1-seasons.ts.
// Importers should call `availableSeasons()` directly so SSR vs CSR rendering
// stays consistent with the user's clock at render time.
export { availableSeasons as f1Seasons, defaultSeason } from "@/lib/f1-seasons";

export const SESSIONS = [
  { id: "R",   label: "Race" },
  { id: "Q",   label: "Qualifying" },
  { id: "FP3", label: "FP3" },
  { id: "FP2", label: "FP2" },
  { id: "FP1", label: "FP1" },
] as const;
export type SessionId = (typeof SESSIONS)[number]["id"];

export const FALLBACK_DRIVERS = [
  "VER", "HAM", "LEC", "NOR", "SAI", "RUS", "PIA", "ALO",
  "STR", "PER", "GAS", "OCO", "TSU", "ALB", "HUL", "MAG",
  "BOT", "ZHO", "SAR", "RIC",
] as const;

export const HOME_ICON_D = "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z";
export const TELEMETRY_ICON_D = "M3 3v18h18M7 16l4-4 4 4 5-8";
