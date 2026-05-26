import type { EvalStatus } from "@/lib/eval-status";

const stops = [
  {
    pct: "40%",
    label: "Baseline",
    body: "Pit-window heuristic shipped against a 5-fixture seed set. Useful enough to demo, but the pit-lap calls drifted on long stints.",
  },
  {
    pct: "65%",
    label: "Tier rework",
    body: "Re-bucketed the tyre-deg tiers and pinned the window to lap-count, not constants. CI snapshot expanded to 20 fixtures.",
  },
  {
    pct: "92%",
    label: "Live gate",
    body: "25-fixture snapshot now gates merges. Failures regenerate from FastF1 lap data; rationale is grounded in a regulation-aware corpus.",
  },
];

export function EvalArcSection({ evalStatus }: { evalStatus: EvalStatus }) {
  const { passing, total, percent, lastUpdated } = evalStatus;

  return (
    <section id="eval-arc" className="py-20">
      <div className="grid gap-10 lg:grid-cols-[1fr_360px] lg:items-start">
        {/* Left: arc narrative */}
        <div>
          <p className="label mb-2">Eval-driven, not vibe-driven</p>
          <h2 className="display mb-6 text-[length:var(--text-h1)] text-foreground">
            How we got here.
          </h2>
          <p className="mb-10 max-w-2xl text-[length:var(--text-body)] leading-7 text-foreground-dim">
            Every step of the strategy heuristic was gated by a snapshot eval that derives ground
            truth from FastF1 lap data — no hand-tuned numbers, no &quot;trust me&quot; metrics.
          </p>

          <ol className="grid gap-px border border-border">
            {stops.map((stop, idx) => (
              <li key={stop.pct} className="grid grid-cols-[80px_1fr_auto] items-baseline gap-4 bg-surface px-5 py-5 sm:grid-cols-[120px_1fr_auto]">
                <p className="display text-[length:var(--text-h2)] text-foreground">{stop.pct}</p>
                <div>
                  <p className="label mb-1">{stop.label}</p>
                  <p className="text-[length:var(--text-small)] leading-6 text-foreground-dim">{stop.body}</p>
                </div>
                <span className="readout text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] text-foreground-faint">
                  {String(idx + 1).padStart(2, "0")}
                </span>
              </li>
            ))}
          </ol>
        </div>

        {/* Right: live readout from the JSON the CI gate enforces */}
        <aside className="card card--elevated p-6">
          <div className="flex items-center justify-between border-b border-border pb-4">
            <p className="label">Snapshot status</p>
            <span className="readout border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 text-[0.55rem] uppercase tracking-[var(--track-wide)] text-emerald-400">
              CI gate
            </span>
          </div>

          <p className="display mt-4 text-[length:var(--text-h1)] text-foreground">{percent}%</p>
          <p className="readout mb-5 text-[length:var(--text-readout)] text-foreground-dim">
            {passing}/{total} pit-window fixtures within ±2 laps
          </p>

          <div className="relative h-2 overflow-hidden border border-border bg-surface">
            <div
              className="absolute inset-y-0 left-0 bg-accent"
              style={{ width: `${percent}%` }}
              aria-hidden
            />
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-4">
            <div>
              <dt className="label mb-1">Passing</dt>
              <dd className="readout text-[length:var(--text-small)] font-semibold text-foreground">{passing}</dd>
            </div>
            <div>
              <dt className="label mb-1">Total</dt>
              <dd className="readout text-[length:var(--text-small)] font-semibold text-foreground">{total}</dd>
            </div>
            <div className="col-span-2">
              <dt className="label mb-1">Last updated</dt>
              <dd className="readout text-[length:var(--text-small)] text-foreground-dim">{lastUpdated}</dd>
            </div>
          </dl>
        </aside>
      </div>
    </section>
  );
}
