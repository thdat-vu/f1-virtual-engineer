"use client";

import { useEffect, useState } from "react";
import type { KnowledgeCitation, KnowledgeNote } from "@/services/api";
import { getKnowledgeNote } from "@/services/api";

// Slice C of the Knowledge / RAG capability (#198). Renders the citation
// list as click-able chips. Selecting a chip expands an inline panel with
// the untruncated note body fetched from `/knowledge/note/{id}`. Falls back
// to the snippet already on the citation if the fetch fails — the chip is
// always informative even when the popover request can't complete.
//
// Empty-state semantics:
//   - `items` undefined  → no analyze run yet, render nothing.
//   - `items` empty []   → analyze completed without RAG hits, render a
//                          subtle "No matching precedent" line so the user
//                          knows the system looked.

export function ReferencesPanel({ items }: { items?: KnowledgeCitation[] }) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeNote, setActiveNote] = useState<KnowledgeNote | null>(null);
  const [loading, setLoading] = useState(false);

  // Derive the active citation from the current `items` list — a stale
  // `activeId` (e.g. from a previous analyze run) silently falls out
  // because `find` returns undefined, so we don't need a reset effect.
  const activeCitation = activeId
    ? items?.find((c) => c.id === activeId)
    : undefined;

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    getKnowledgeNote(activeId).then((note) => {
      if (cancelled) return;
      setActiveNote(note);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  if (!items) return null;

  if (items.length === 0) {
    return (
      <div className="mb-4 mt-4 border-l-2 border-border bg-surface-elevated/40 px-3 py-2">
        <p className="readout text-[0.65rem] text-foreground-faint">
          No matching precedent for this call.
        </p>
      </div>
    );
  }

  // Loading + reset live in the click handler rather than inside an effect
  // so we don't trip react-hooks/set-state-in-effect (eslint plugin flags
  // any synchronous setState in an effect body).
  const handleSelect = (id: string) => {
    if (id === activeId) {
      setActiveId(null);
      setActiveNote(null);
      setLoading(false);
      return;
    }
    setActiveId(id);
    setActiveNote(null);
    setLoading(true);
  };

  return (
    <div className="mb-4 mt-4 border-l-2 border-accent bg-accent-dim/30 px-3 py-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
        <p className="label text-accent">References</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {items.map((c) => {
          const isActive = c.id === activeId;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => handleSelect(c.id)}
              aria-expanded={isActive}
              aria-controls={isActive ? `citation-body-${c.id}` : undefined}
              className={`readout flex items-center gap-1.5 border px-2 py-1 text-[0.6rem] uppercase tracking-wide transition-colors ${
                isActive
                  ? "border-accent bg-accent-dim/60 text-foreground"
                  : "border-border bg-surface-elevated text-foreground-dim hover:border-accent/60 hover:text-foreground"
              }`}
            >
              <span
                className="h-1 w-1 rounded-full"
                style={{
                  backgroundColor:
                    c.score >= 2 ? "var(--accent)" : "var(--foreground-faint)",
                }}
                aria-hidden
              />
              <span>{c.title}</span>
            </button>
          );
        })}
      </div>

      {activeCitation && (
        <div
          id={`citation-body-${activeCitation.id}`}
          role="region"
          aria-label={`Full text for ${activeCitation.title}`}
          className="mt-3 border border-border bg-background/60 px-3 py-2"
        >
          {activeCitation.section && (
            <p className="readout text-[0.55rem] uppercase tracking-wide text-foreground-faint">
              {activeCitation.section}
            </p>
          )}
          <p className="readout mt-1 text-[0.7rem] font-semibold uppercase leading-snug text-foreground">
            {activeCitation.title}
          </p>
          {activeCitation.source && (
            <p className="readout mt-0.5 text-[0.55rem] text-foreground-faint">
              {activeCitation.source}
            </p>
          )}
          <p className="readout mt-2 whitespace-pre-line text-[0.7rem] leading-relaxed text-foreground-dim">
            {loading
              ? "Loading…"
              : (activeNote?.body ?? activeCitation.snippet)}
          </p>
        </div>
      )}
    </div>
  );
}
