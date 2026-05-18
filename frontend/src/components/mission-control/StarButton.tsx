"use client";

import { useCallback, useMemo } from "react";
import type { Session } from "@supabase/supabase-js";
import { useSupabase } from "@/components/auth/SupabaseProvider";
import {
  createSavedQuery,
  deleteSavedQuery,
  type SavedQueryItem,
  type SavedQueryKind,
} from "@/services/api";

type Props = {
  kind: SavedQueryKind;
  payload: Record<string, unknown>;
  canSave: boolean;
  savedQueries: SavedQueryItem[];
  onChange: (next: SavedQueryItem[]) => void;
};

function payloadsEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(normalize(a)) === JSON.stringify(normalize(b));
}

/**
 * Strip null/undefined/empty-string values and recurse into objects so
 * payloads that differ only in "absent vs explicit empty" still match.
 *
 * Why: existing rows were written before the compare_driver field
 * existed, so their payloads have no `compare_driver` key. New writes
 * always include `compare_driver: null` (or a real string). Without
 * normalization, the StarButton's "is this current selection saved?"
 * check would never match those legacy rows again.
 */
function normalize(value: unknown): unknown {
  if (value === null || value === undefined || value === "") return undefined;
  if (Array.isArray(value)) return value.map(normalize);
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const n = normalize(v);
      if (n !== undefined) out[k] = n;
    }
    // Sort keys so {a,b} and {b,a} stringify identically.
    return Object.fromEntries(Object.entries(out).sort(([a], [b]) => a.localeCompare(b)));
  }
  return value;
}

export function StarButton({ kind, payload, canSave, savedQueries, onChange }: Props) {
  const { session } = useSupabase();
  const match = useMemo(
    () => savedQueries.find((q) => q.kind === kind && payloadsEqual(q.payload, payload)),
    [savedQueries, kind, payload],
  );

  const toggle = useCallback(async () => {
    if (!session || !canSave) return;
    try {
      if (match) {
        await deleteSavedQuery(session.access_token, match.id);
        onChange(savedQueries.filter((q) => q.id !== match.id));
      } else {
        const row = await createSavedQueryWithSession(session, kind, payload);
        onChange([row, ...savedQueries]);
      }
    } catch {
      // Swallow — the UI falls back to the next refresh.
    }
  }, [session, canSave, match, onChange, savedQueries, kind, payload]);

  if (!session) return null;

  const filled = !!match;
  const disabled = !canSave;
  const label = filled ? "Unstar saved query" : "Star current query";

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      aria-label={label}
      aria-pressed={filled}
      title={label}
      className={`shrink-0 border px-2 py-1 transition-colors duration-[var(--dur-fast)] disabled:cursor-not-allowed disabled:opacity-30 ${
        filled
          ? "border-accent bg-accent-dim text-accent"
          : "border-border text-foreground-dim hover:border-accent hover:text-accent"
      }`}
    >
      <StarIcon filled={filled} />
    </button>
  );
}

async function createSavedQueryWithSession(
  session: Session,
  kind: SavedQueryKind,
  payload: Record<string, unknown>,
) {
  return createSavedQuery(session.access_token, { kind, payload });
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}
