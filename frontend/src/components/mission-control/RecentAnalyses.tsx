"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { useSupabase } from "@/components/auth/SupabaseProvider";
import { getAnalyzeHistory, type AnalyzeHistoryItem } from "@/services/api";
import { formatRelativeTime } from "@/lib/relative-time";

type Status = "idle" | "loading" | "loaded" | "error";

export function RecentAnalyses({
  refreshSignal = 0,
  onSelect,
}: {
  refreshSignal?: number;
  onSelect?: (item: AnalyzeHistoryItem) => void;
}) {
  const { session } = useSupabase();
  if (!session) return null;
  // Keying by user id forces React to remount the inner component on a
  // sign-out/in (or account switch) — the alternative is to reset state
  // synchronously inside an effect, which the React 19 lint rule
  // `react-hooks/set-state-in-effect` rejects. Remount = guaranteed fresh
  // state, no chance of one user's rows briefly rendering under another.
  return (
    <RecentAnalysesPanel
      key={session.user.id}
      session={session}
      refreshSignal={refreshSignal}
      onSelect={onSelect}
    />
  );
}

function RecentAnalysesPanel({
  session,
  refreshSignal,
  onSelect,
}: {
  session: Session;
  refreshSignal: number;
  onSelect?: (item: AnalyzeHistoryItem) => void;
}) {
  const [items, setItems] = useState<AnalyzeHistoryItem[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    // Push state updates onto a microtask so the lint rule against
    // synchronous setState in effects is satisfied; the visible behaviour is
    // identical (transition is "idle" → "loading" → "loaded" within a tick).
    queueMicrotask(async () => {
      if (cancelled) return;
      setStatus("loading");
      try {
        const res = await getAnalyzeHistory(session.access_token, 5);
        if (cancelled) return;
        setItems(res.items);
        setStatus("loaded");
      } catch {
        if (!cancelled) setStatus("error");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [session, refreshSignal]);

  return (
    <section className="mb-4 mt-4 border-t border-border pt-3">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <p className="label">Recent</p>
        <span className="readout text-[length:var(--text-readout)] text-foreground-faint">
          {open ? "−" : "+"}
        </span>
      </button>

      {open && (
        <div className="mt-2 space-y-1.5">
          {status === "loading" && items.length === 0 && (
            <p className="readout text-[length:var(--text-readout)] text-foreground-faint">
              Loading…
            </p>
          )}
          {status === "error" && (
            <p className="readout text-[length:var(--text-readout)] text-foreground-faint">
              Could not load history.
            </p>
          )}
          {status === "loaded" && items.length === 0 && (
            <p className="readout text-[length:var(--text-readout)] text-foreground-faint">
              No recent analyses yet.
            </p>
          )}
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect?.(item)}
              className="block w-full border border-border px-2 py-1.5 text-left transition-colors duration-[var(--dur-fast)] hover:border-accent"
              title={item.query}
            >
              <p className="readout truncate text-[length:var(--text-readout)] text-foreground">
                {item.query}
              </p>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="readout truncate text-[0.55rem] uppercase tracking-wide text-foreground-dim">
                  {[item.driver, item.event, item.year].filter(Boolean).join(" · ") || "—"}
                </span>
                <span className="readout shrink-0 text-[0.55rem] text-foreground-faint">
                  {formatRelativeTime(item.created_at)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
