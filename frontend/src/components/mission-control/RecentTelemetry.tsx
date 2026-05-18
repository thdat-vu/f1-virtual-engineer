"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { useSupabase } from "@/components/auth/SupabaseProvider";
import { getTelemetryHistory, type TelemetryHistoryItem } from "@/services/api";
import { formatRelativeTime } from "@/lib/relative-time";

type Status = "idle" | "loading" | "loaded" | "error";

export function RecentTelemetry({
  refreshSignal = 0,
  onSelect,
}: {
  refreshSignal?: number;
  onSelect?: (item: TelemetryHistoryItem) => void;
}) {
  const { session } = useSupabase();
  if (!session) return null;
  // Same remount-on-identity pattern as RecentAnalyses: keying by user id
  // guarantees a fresh state if the signed-in account changes.
  return (
    <RecentTelemetryPanel
      key={session.user.id}
      session={session}
      refreshSignal={refreshSignal}
      onSelect={onSelect}
    />
  );
}

function RecentTelemetryPanel({
  session,
  refreshSignal,
  onSelect,
}: {
  session: Session;
  refreshSignal: number;
  onSelect?: (item: TelemetryHistoryItem) => void;
}) {
  const [items, setItems] = useState<TelemetryHistoryItem[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(async () => {
      if (cancelled) return;
      setStatus("loading");
      try {
        const res = await getTelemetryHistory(session.access_token, 5);
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
        <p className="label">Recently viewed</p>
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
              No telemetry lookups yet.
            </p>
          )}
          {items.map((item) => {
            const head = `${item.driver} · ${item.session_type}`;
            const tail = [item.event, item.year].filter(Boolean).join(" · ");
            const lap = item.lap_number != null ? `Lap ${item.lap_number}` : "Fastest lap";
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect?.(item)}
                className="block w-full border border-border px-2 py-1.5 text-left transition-colors duration-[var(--dur-fast)] hover:border-accent"
                title={`${head} · ${tail} · ${lap}`}
              >
                <p className="readout truncate text-[length:var(--text-readout)] text-foreground">
                  {head}
                </p>
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="readout truncate text-[0.55rem] uppercase tracking-wide text-foreground-dim">
                    {[tail, lap].filter(Boolean).join(" · ") || "—"}
                  </span>
                  <span className="readout shrink-0 text-[0.55rem] text-foreground-faint">
                    {formatRelativeTime(item.created_at)}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
