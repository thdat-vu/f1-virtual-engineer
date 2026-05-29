interface BoxBoxEmptyProps {
  message: string;
  hint?: string;
}

export function BoxBoxEmpty({ message, hint }: BoxBoxEmptyProps) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 text-center">
      <span className="readout border border-red-500/40 bg-red-500/10 px-2 py-0.5 text-[0.55rem] uppercase tracking-[var(--track-wide)] text-red-400">
        BOX BOX
      </span>
      <span className="readout text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-faint">
        {message}
      </span>
      {hint && (
        <span className="readout text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground-faint/70">
          {hint}
        </span>
      )}
    </div>
  );
}
