const capabilityItems = [
  {
    id: "01",
    label: "Telemetry Analysis",
    title: "Compare speed, gear, and RPM across race sessions.",
    body: "Turn raw FastF1 data into readable performance signals — no manual chart parsing.",
  },
  {
    id: "02",
    label: "Tyre Intelligence",
    title: "Read tyre decay before the pace cliff hits.",
    body: "Surface lap-time decay, compound context, and degradation signals as strategy-ready insight.",
  },
  {
    id: "03",
    label: "Pit Strategy",
    title: "Spot undercut windows and strategic risk earlier.",
    body: "Translate telemetry, gaps, and session context into explainable pit-window recommendations.",
  },
  {
    id: "04",
    label: "Race Narrative",
    title: "Understand why the recommendation exists.",
    body: "Show assumptions, fallback behavior, and reasoning — not hand-wavy AI output.",
  },
];

export function CapabilityGrid() {
  return (
    <div className="grid gap-px border border-border md:grid-cols-2 xl:grid-cols-4">
      {capabilityItems.map((item) => (
        <article
          key={item.id}
          className="group bg-surface p-6 transition-colors"
        >
          <div className="mb-6 flex items-start justify-between">
            <span className="label">{item.label}</span>
            <span className="readout text-[length:var(--text-label)] text-foreground-faint">
              {item.id}
            </span>
          </div>
          <div className="mb-4 h-px w-6 bg-accent transition-all duration-300 group-hover:w-12" />
          <h3 className="mb-3 text-[length:var(--text-h3)] font-semibold leading-snug text-foreground">
            {item.title}
          </h3>
          <p className="readout text-[length:var(--text-readout)] leading-5 text-foreground-dim">
            {item.body}
          </p>
        </article>
      ))}
    </div>
  );
}
