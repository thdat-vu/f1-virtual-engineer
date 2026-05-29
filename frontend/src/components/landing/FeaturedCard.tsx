import Link from "next/link";
import featured from "@/content/featured.json";

interface FeaturedEntry {
  enabled: boolean;
  headline: string;
  story: string;
  cta: string;
  event: string;
  session: string;
  driver: string;
  lap: string;
}

export function FeaturedCard() {
  const entry = featured as FeaturedEntry;
  if (!entry.enabled || !entry.headline) return null;

  const href =
    `/mission-control?event=${encodeURIComponent(entry.event)}` +
    `&session=${entry.session}` +
    `&driver=${entry.driver}` +
    `&lap=${entry.lap}`;

  return (
    <section aria-labelledby="featured-heading" className="py-10">
      <div className="card card--elevated relative overflow-hidden border-l-2 border-l-[var(--accent)] p-6 md:p-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="max-w-2xl">
            <p className="label mb-3 text-[var(--accent)]">Featured this week</p>
            <h2
              id="featured-heading"
              className="display mb-3 text-[length:var(--text-h2)] leading-tight text-foreground"
            >
              {entry.headline}
            </h2>
            <p className="text-[length:var(--text-body)] leading-7 text-foreground-dim">
              {entry.story}
            </p>
          </div>
          <Link href={href} className="btn btn--invert shrink-0">
            {entry.cta} →
          </Link>
        </div>
      </div>
    </section>
  );
}
