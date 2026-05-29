import Image from "next/image";
import Link from "next/link";
import { CapabilityGrid } from "@/components/landing/CapabilityGrid";
import { EvalArcSection } from "@/components/landing/EvalArcSection";
import { LandingCTA } from "@/components/landing/LandingCTA";
import { LandingHero } from "@/components/landing/LandingHero";
import { RaceWeekendPill } from "@/components/landing/RaceWeekendPill";
import { TeamSwitcher } from "@/components/landing/TeamSwitcher";
import { Footer } from "@/components/Footer";
import { readEvalStatus } from "@/lib/eval-status";

const navItems = [
  { label: "Capabilities", href: "#capabilities" },
  { label: "How it's built", href: "#eval-arc" },
  { label: "Mission Control", href: "/mission-control" },
];

export default function Home() {
  // Server Component — runs at build time. The reader uses node:fs and
  // never reaches the client bundle. See frontend/src/lib/eval-status.ts.
  const evalStatus = readEvalStatus();

  return (
    <main id="top" className="min-h-screen overflow-x-hidden bg-background text-foreground">
      <div className="hero-glow pointer-events-none fixed inset-0 opacity-60" />

      <header className="sticky top-0 z-50 border-b border-border bg-overlay backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Image
              src="/icon.png"
              alt="F1 Virtual Engineer"
              width={32}
              height={32}
              priority
              className="h-8 w-8 rounded-sm"
            />
            <div>
              <p className="text-[0.7rem] font-bold uppercase tracking-[var(--track-wide)] text-foreground">
                F1 Virtual Engineer
              </p>
              <p className="readout text-[0.55rem] uppercase tracking-[var(--track-widest)] text-foreground-dim">
                Telemetry · Strategy · Explainable AI
              </p>
            </div>
          </div>

          <nav className="hidden items-center gap-8 md:flex">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="readout text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-dim transition-colors hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-4">
            <RaceWeekendPill />
            <TeamSwitcher />
            <Link href="/mission-control" className="btn btn--accent">
              Launch
            </Link>
          </div>
        </div>
      </header>

      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <LandingHero />

        <section id="capabilities" className="py-20">
          <div className="mb-10">
            <p className="label mb-2">Core capabilities</p>
            <h2 className="display text-[length:var(--text-h1)] text-foreground">
              Telemetry → Decision. No guesswork.
            </h2>
          </div>
          <CapabilityGrid />
        </section>

        <EvalArcSection evalStatus={evalStatus} />
      </div>

      <LandingCTA />
      <Footer />
    </main>
  );
}
