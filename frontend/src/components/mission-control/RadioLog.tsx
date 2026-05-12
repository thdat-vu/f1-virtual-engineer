"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { useSupabase } from "@/components/auth/SupabaseProvider";
import { getRadioHistory, type RadioHistoryItem } from "@/services/api";
import { formatRelativeTime } from "@/lib/relative-time";

type Status = "idle" | "loading" | "loaded" | "error";

const SEVERITY_STYLE: Record<string, { bar: string; pill: string }> = {
  high:   { bar: "bg-red-500",    pill: "bg-red-500/20 text-red-300 border-red-500/40" },
  medium: { bar: "bg-amber-400",  pill: "bg-amber-400/15 text-amber-300 border-amber-400/40" },
  low:    { bar: "bg-accent",     pill: "bg-accent-dim text-accent border-accent/40" },
};

const DEFAULT_STYLE = {
  bar: "bg-border",
  pill: "bg-surface text-foreground-dim border-border",
};

export function RadioLog({ refreshSignal = 0 }: { refreshSignal?: number }) {
  const { session } = useSupabase();
  if (!session) return null;
  return (
    <RadioLogPanel key={session.user.id} session={session} refreshSignal={refreshSignal} />
  );
}

function RadioLogPanel({
  session,
  refreshSignal,
}: {
  session: Session;
  refreshSignal: number;
}) {
  const [items, setItems] = useState<RadioHistoryItem[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [open, setOpen] = useState(true);
  const [driverFilter, setDriverFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(async () => {
      if (cancelled) return;
      setStatus("loading");
      try {
        const res = await getRadioHistory(
          session.access_token,
          20,
          driverFilter.trim().toUpperCase() || undefined,
        );
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
  }, [session, refreshSignal, driverFilter]);

  return (
    <section className="mb-4 mt-4 border-t border-border pt-3">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <span className="inline-block h-1.5 w-1.5 bg-accent" aria-hidden />
          <p className="label text-accent">Radio Log</p>
        </div>
        <span className="readout text-[length:var(--text-readout)] text-foreground-faint">
          {open ? "−" : "+"}
        </span>
      </button>

      {open && (
        <div className="mt-2 space-y-1.5">
          <input
            type="text"
            value={driverFilter}
            onChange={(e) => setDriverFilter(e.target.value)}
            placeholder="Filter by driver (e.g. VER)"
            maxLength={3}
            className="w-full border border-border bg-transparent px-2 py-1 readout text-[length:var(--text-readout)] text-foreground placeholder:text-foreground-faint focus:border-accent focus:outline-none"
            aria-label="Filter radio log by driver code"
          />

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
              No radio classifications yet.
            </p>
          )}

          {items.map((item) => {
            const style = SEVERITY_STYLE[item.severity] ?? DEFAULT_STYLE;
            return (
              <div
                key={item.id}
                className="relative border border-border bg-accent-dim/40 pl-2.5 pr-2 py-1.5 transition-colors duration-[var(--dur-fast)] hover:border-accent"
              >
                <span
                  className={`absolute left-0 top-0 h-full w-0.5 ${style.bar}`}
                  aria-hidden
                />
                <div className="flex items-center justify-between gap-2">
                  <span className="readout text-[length:var(--text-readout)] font-bold uppercase tracking-wide text-accent">
                    {item.classification.replace("_", " ")}
                  </span>
                  <span
                    className={`readout inline-block border px-1.5 py-[1px] text-[0.5rem] uppercase tracking-[0.1em] ${style.pill}`}
                  >
                    {item.severity}
                  </span>
                </div>
                {item.trigger_phrase && (
                  <p className="readout mt-1 truncate text-[0.6rem] italic text-foreground-dim">
                    &ldquo;{item.trigger_phrase}&rdquo;
                  </p>
                )}
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="readout truncate text-[0.55rem] uppercase tracking-wide text-foreground-dim">
                    {item.driver ?? "—"}
                  </span>
                  <span className="readout shrink-0 text-[0.55rem] text-foreground-faint">
                    {formatRelativeTime(item.created_at)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
