import Image from "next/image";
import Link from "next/link";

interface CapabilityItem {
  id: string;
  label: string;
  title: string;
  body: string;
  href: string;
  screenshot: string;
  screenshotAlt: string;
}

const capabilityItems: CapabilityItem[] = [
  {
    id: "01",
    label: "Telemetry + Lap Delta",
    title: "Compare two drivers, lap-by-lap, distance-by-distance.",
    body: "Speed, gear, RPM and per-distance Δt — VER vs HAM at Japan, no manual chart parsing.",
    href: "/mission-control?event=Japanese%20Grand%20Prix&session=R&driver=VER&compareDriver=HAM",
    screenshot: "/landing/screenshot-telemetry-lap-delta.png",
    screenshotAlt: "Mission Control showing VER vs HAM telemetry and lap-delta charts at the Japanese Grand Prix",
  },
  {
    id: "02",
    label: "Strategy Compare",
    title: "What-if pit calls, side by side.",
    body: "Pit-window recommendations with target-driver gap context, tyre features, and rationale you can read.",
    href: "/mission-control?intent=strategy&event=Japanese%20Grand%20Prix&driver=VER&compareDriver=HAM",
    screenshot: "/landing/screenshot-strategy-compare.png",
    screenshotAlt: "Strategy compare view with side-by-side what-if pit window cards",
  },
  {
    id: "03",
    label: "Cross-Year + Citation",
    title: "Same driver, two seasons, one delta line.",
    body: "Compare a driver's fastest lap year-over-year with citations from a regulation-aware corpus.",
    href: "/mission-control?event=Japanese%20Grand%20Prix&driver=VER&compareYear=2023",
    screenshot: "/landing/screenshot-cross-year.png",
    screenshotAlt: "Cross-year comparison VER 2024 vs 2023 with the citation chip open",
  },
  {
    id: "04",
    label: "Weather + Tyre Context",
    title: "Conditions in the header, compound history in the card.",
    body: "Per-session weather pill (DRY / MIXED / WET) with tyre framing — the context strategy actually depends on.",
    href: "/mission-control",
    screenshot: "/landing/screenshot-weather-tyre.png",
    screenshotAlt: "Mission Control header weather pill and tyre context card",
  },
];

export function CapabilityGrid() {
  return (
    <div className="grid gap-px border border-border md:grid-cols-2 xl:grid-cols-2">
      {capabilityItems.map((item) => (
        <Link
          key={item.id}
          href={item.href}
          className="group flex flex-col bg-surface transition-colors hover:bg-surface-elevated"
        >
          {/* Screenshots are authored manually — see frontend/public/landing/README.md. */}
          <div className="relative aspect-[2/1] overflow-hidden border-b border-border bg-surface-elevated">
            <Image
              src={item.screenshot}
              alt={item.screenshotAlt}
              fill
              sizes="(min-width: 1280px) 600px, (min-width: 768px) 50vw, 100vw"
              className="object-cover opacity-90 transition-opacity group-hover:opacity-100"
              loading="lazy"
            />
          </div>

          <div className="p-6">
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
          </div>
        </Link>
      ))}
    </div>
  );
}
