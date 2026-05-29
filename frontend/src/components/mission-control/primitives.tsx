"use client";

import { useEffect, useRef, useState } from "react";

export function NavIcon({ d }: { d: string }) {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

export function VDivider({ height = 5 }: { height?: number }) {
  return <div className="w-px shrink-0 bg-border" style={{ height: `${height * 0.25}rem` }} />;
}

// Custom Listbox replaces the native <select>. Native dropdowns can't
// style their scrollbar (the OS owns it), which clashed with the
// monochrome readout theme. This re-implements the pieces we need —
// keyboard nav, click-outside dismiss, scrollable list — without
// pulling in a UI lib. Same Select() signature so callsites don't
// change.
export function Select<T extends string>({
  value, onChange, options, loading, placeholder,
}: {
  value: T | "";
  onChange: (v: T) => void;
  options: { id: T; label: string }[];
  loading?: boolean;
  placeholder: string;
}) {
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState<number>(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selectedIdx = options.findIndex((o) => o.id === value);
  const display = value
    ? options[selectedIdx]?.label ?? value
    : loading ? "Loading…" : placeholder;

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); return; }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlight((i) => Math.min(options.length - 1, i + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlight((i) => Math.max(0, i - 1));
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const opt = options[highlight];
        if (opt) { onChange(opt.id); setOpen(false); }
      } else if (e.key === "Home") {
        e.preventDefault(); setHighlight(0);
      } else if (e.key === "End") {
        e.preventDefault(); setHighlight(options.length - 1);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, options, highlight, onChange]);

  useEffect(() => {
    if (!open || !listRef.current || highlight < 0) return;
    const el = listRef.current.children[highlight] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [highlight, open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        disabled={loading}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => {
            const next = !v;
            if (next) setHighlight(selectedIdx >= 0 ? selectedIdx : 0);
            return next;
          });
        }}
        className="readout flex w-full cursor-pointer items-center justify-between border border-border bg-surface-elevated pl-3 pr-2 py-1.5 text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] outline-none transition-colors focus-visible:border-accent disabled:cursor-not-allowed disabled:opacity-40"
        style={{
          color: value ? "var(--foreground)" : "var(--foreground-dim)",
          minWidth: "9rem",
        }}
      >
        <span className="truncate">{display}</span>
        <svg width="8" height="8" viewBox="0 0 8 8" fill="none" className="ml-2 shrink-0 opacity-50">
          <path d="M1 3l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <ul
          ref={listRef}
          role="listbox"
          tabIndex={-1}
          className="readout mc-listbox absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-y-auto border border-border bg-surface-elevated text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] shadow-lg"
        >
          {options.length === 0 && (
            <li className="px-3 py-2 text-foreground-dim">No options</li>
          )}
          {options.map((o, i) => {
            const isSelected = o.id === value;
            const isHi = i === highlight;
            return (
              <li
                key={o.id}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={(e) => { e.preventDefault(); onChange(o.id); setOpen(false); }}
                className={`cursor-pointer px-3 py-1.5 transition-colors ${
                  isHi
                    ? "bg-[var(--accent-dim)] text-foreground"
                    : "text-foreground-dim hover:text-foreground"
                }`}
              >
                {o.label}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
