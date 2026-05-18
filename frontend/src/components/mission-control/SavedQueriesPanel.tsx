"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { useSupabase } from "@/components/auth/SupabaseProvider";
import {
  deleteSavedQuery,
  getSavedQueries,
  type SavedQueryItem,
} from "@/services/api";
import { formatRelativeTime } from "@/lib/relative-time";

type Status = "idle" | "loading" | "loaded" | "error";

export function SavedQueriesPanel({
  items,
  onItemsChange,
  onSelect,
}: {
  items: SavedQueryItem[];
  onItemsChange: (items: SavedQueryItem[]) => void;
  onSelect?: (item: SavedQueryItem) => void;
}) {
  const { session } = useSupabase();
  if (!session) return null;
  return (
    <SavedQueriesInner
      key={session.user.id}
      session={session}
      items={items}
      onItemsChange={onItemsChange}
      onSelect={onSelect}
    />
  );
}

function SavedQueriesInner({
  session,
  items,
  onItemsChange,
  onSelect,
}: {
  session: Session;
  items: SavedQueryItem[];
  onItemsChange: (items: SavedQueryItem[]) => void;
  onSelect?: (item: SavedQueryItem) => void;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(async () => {
      if (cancelled) return;
      setStatus("loading");
      try {
        const res = await getSavedQueries(session.access_token, 50);
        if (cancelled) return;
        onItemsChange(res.items);
        setStatus("loaded");
      } catch {
        if (!cancelled) setStatus("error");
      }
    });
    return () => {
      cancelled = true;
    };
    // onItemsChange intentionally excluded — it's a stable setter wrapper; depending on it would refetch on every change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const remove = async (id: string) => {
    try {
      await deleteSavedQuery(session.access_token, id);
      onItemsChange(items.filter((i) => i.id !== id));
    } catch {
      // Silent — next refresh will reconcile.
    }
  };

  return (
    <section className="mb-4 mt-4 border-t border-border pt-3">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <p className="label">Saved</p>
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
              Could not load saved queries.
            </p>
          )}
          {status === "loaded" && items.length === 0 && (
            <p className="readout text-[length:var(--text-readout)] text-foreground-faint">
              No saved queries yet.
            </p>
          )}

          {items.map((item) => (
            <SavedRow
              key={item.id}
              item={item}
              onSelect={onSelect}
              onDelete={() => remove(item.id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function SavedRow({
  item,
  onSelect,
  onDelete,
}: {
  item: SavedQueryItem;
  onSelect?: (item: SavedQueryItem) => void;
  onDelete: () => void;
}) {
  const head = item.label ?? deriveLabel(item);
  const meta = deriveMeta(item);

  return (
    <div className="group relative border border-border px-2 py-1.5 transition-colors duration-[var(--dur-fast)] hover:border-accent">
      <button
        type="button"
        onClick={() => onSelect?.(item)}
        className="block w-full text-left"
        title={head}
      >
        <div className="flex items-center gap-2">
          <span className="readout inline-block border border-accent/40 bg-accent-dim px-1 py-[1px] text-[0.5rem] uppercase tracking-[0.1em] text-accent">
            {item.kind}
          </span>
          <p className="readout truncate text-[length:var(--text-readout)] text-foreground">
            {head}
          </p>
        </div>
        <div className="mt-1 flex items-center justify-between gap-2">
          <span className="readout truncate text-[0.55rem] uppercase tracking-wide text-foreground-dim">
            {meta || "—"}
          </span>
          <span className="readout shrink-0 text-[0.55rem] text-foreground-faint">
            {formatRelativeTime(item.created_at)}
          </span>
        </div>
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        aria-label="Delete saved query"
        className="absolute right-1 top-1 px-1 text-[0.7rem] text-foreground-faint opacity-0 transition-opacity duration-[var(--dur-fast)] hover:text-accent group-hover:opacity-100"
        title="Delete"
      >
        ×
      </button>
    </div>
  );
}

function deriveLabel(item: SavedQueryItem): string {
  const p = item.payload as Record<string, unknown>;
  if (item.kind === "analyze") {
    const q = typeof p.query === "string" ? p.query : null;
    return q ?? "Saved analyze";
  }
  const driver = typeof p.driver === "string" ? p.driver : "?";
  const event = typeof p.event === "string" ? p.event : "?";
  return `${driver} · ${event}`;
}

function deriveMeta(item: SavedQueryItem): string {
  const p = item.payload as Record<string, unknown>;
  const parts: string[] = [];
  if (item.kind === "analyze") {
    const info = (p.session_info as Record<string, unknown> | undefined) ?? {};
    const driver = typeof p.driver === "string" ? p.driver : null;
    const compare = typeof p.compare_driver === "string" ? p.compare_driver : null;
    const event = typeof info.event === "string" ? info.event : null;
    const year = typeof info.year === "number" ? info.year : null;
    if (driver) parts.push(compare ? `${driver} vs ${compare}` : driver);
    if (event) parts.push(event);
    if (year != null) parts.push(String(year));
  } else {
    const driver = typeof p.driver === "string" ? p.driver : null;
    const event = typeof p.event === "string" ? p.event : null;
    const year = typeof p.year === "number" ? p.year : null;
    const lap = typeof p.lap_number === "number" ? `Lap ${p.lap_number}` : "Fastest";
    if (driver) parts.push(driver);
    if (event) parts.push(event);
    if (year != null) parts.push(String(year));
    parts.push(lap);
  }
  return parts.join(" · ");
}
