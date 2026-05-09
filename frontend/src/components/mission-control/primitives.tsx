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

export function Select<T extends string>({
  value, onChange, options, loading, placeholder,
}: {
  value: T | "";
  onChange: (v: T) => void;
  options: { id: T; label: string }[];
  loading?: boolean;
  placeholder: string;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        disabled={loading}
        className="readout cursor-pointer appearance-none border border-border bg-surface-elevated pl-3 pr-7 py-1.5 text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] outline-none transition-colors focus:border-accent disabled:opacity-40"
        style={{
          color: value ? "var(--foreground)" : "var(--foreground-dim)",
          minWidth: "9rem",
        }}
      >
        <option value="" disabled>{loading ? "Loading…" : placeholder}</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>{o.label}</option>
        ))}
      </select>
      <svg width="8" height="8" viewBox="0 0 8 8" fill="none"
        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 opacity-50">
        <path d="M1 3l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    </div>
  );
}
