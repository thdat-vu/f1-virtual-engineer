"use client";

import { TeamIcon } from "@/components/icons/TeamIcons";
import { TEAMS, type TeamId } from "./constants";

export function MissionHeader({
  displayDriver, displayEvent, displayLap, theme, setTheme,
}: {
  displayDriver: string;
  displayEvent: string;
  displayLap: string | null;
  theme: TeamId;
  setTheme: (id: TeamId) => void;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface px-5">
      <span className="label shrink-0 text-[length:var(--text-readout)]">Mission Control</span>
      <div className="h-3 w-px shrink-0 bg-border-strong" />
      <span className="readout shrink-0 text-[length:var(--text-readout)] text-foreground-dim">
        {displayDriver} {"//"} {displayEvent}{displayLap ? ` // ${displayLap}` : ""}
      </span>
      <div className="flex-1" />

      <div className="flex items-center gap-1.5">
        {TEAMS.map((t) => {
          const active = theme === t.id;
          return (
            <button key={t.id} onClick={() => setTheme(t.id as TeamId)}
              title={t.label}
              className="shrink-0 rounded-sm transition-all duration-[var(--dur-fast)]"
              style={{
                opacity:       active ? 1 : 0.35,
                transform:     active ? "scale(1.5)" : "scale(1)",
                outline:       active ? `1.5px solid ${t.color}` : "none",
                outlineOffset: "2px",
              }}>
              <TeamIcon id={t.id} size={24} />
            </button>
          );
        })}
      </div>
    </header>
  );
}
