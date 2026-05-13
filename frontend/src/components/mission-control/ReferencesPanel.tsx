"use client";

import type { KnowledgeCitation } from "@/services/api";

export function ReferencesPanel({ items }: { items?: KnowledgeCitation[] }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="mb-4 mt-4 border-l-2 border-accent bg-accent-dim/30 px-3 py-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
        <p className="label text-accent">FIA References</p>
      </div>
      <ul className="space-y-2">
        {items.map((c) => (
          <li key={c.id} className="border-l border-border pl-2">
            <p className="readout text-[0.7rem] font-semibold uppercase leading-snug text-foreground">
              {c.title}
            </p>
            {c.section && (
              <p className="readout text-[0.55rem] uppercase tracking-wide text-foreground-faint">
                {c.section}
              </p>
            )}
            <p className="readout mt-1 text-[0.65rem] leading-snug text-foreground-dim">
              {c.snippet}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
