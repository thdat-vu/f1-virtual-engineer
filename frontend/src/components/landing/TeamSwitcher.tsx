"use client";

import { useMissionStore } from "@/lib/store";
import { TeamIcon } from "@/components/icons/TeamIcons";

const TEAMS = [
  { id: "ferrari",     color: "#DC0000" },
  { id: "redbull",     color: "#1E2A78" },
  { id: "mercedes",    color: "#00D2BE" },
  { id: "mclaren",     color: "#FF8700" },
  { id: "alpine",      color: "#1F5EFF" },
  { id: "astonmartin", color: "#006F62" },
  { id: "williams",    color: "#005AFF" },
  { id: "haas",        color: "#B6BABD" },
  { id: "rb",          color: "#6692FF" },
  { id: "audi",        color: "#C8C8C8" },
  { id: "cadillac",    color: "#D4AF37" },
] as const;

type TeamId = (typeof TEAMS)[number]["id"];

export function TeamSwitcher() {
  const { theme, setTheme } = useMissionStore();

  return (
    <div className="flex items-center gap-1.5">
      {TEAMS.map((t) => {
        const active = theme === t.id;
        return (
          <button
            key={t.id}
            onClick={() => setTheme(t.id as TeamId)}
            title={t.id}
            className="shrink-0 rounded-sm transition-all duration-[var(--dur-fast)]"
            style={{
              opacity:       active ? 1 : 0.3,
              transform:     active ? "scale(1.4)" : "scale(1)",
              outline:       active ? `1.5px solid ${t.color}` : "none",
              outlineOffset: "2px",
            }}
          >
            <TeamIcon id={t.id} size={24} />
          </button>
        );
      })}
    </div>
  );
}
