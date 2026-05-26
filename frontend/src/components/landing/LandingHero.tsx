"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { EvalStatus } from "@/lib/eval-status";

function FadeUp({
  delay = 0,
  children,
  className,
}: {
  delay?: number;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.55, ease: [0.22, 0.61, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function LandingHero({ evalStatus }: { evalStatus: EvalStatus }) {
  const heroStats = [
    { label: "Eval pass rate",       value: `${evalStatus.percent}%`,                     hint: "snapshot CI gate" },
    { label: "Fixtures passing",     value: `${evalStatus.passing}/${evalStatus.total}`,  hint: "real F1 races" },
    { label: "Decision latency",     value: "<5s",                                        hint: "telemetry → call" },
  ];

  return (
    <section className="relative overflow-hidden pt-16 pb-20">
      <div className="hero-grid pointer-events-none absolute inset-0 opacity-40" />

      <div className="relative z-10 grid gap-14 lg:grid-cols-[1fr_420px] lg:items-center">
        {/* Left column — copy */}
        <div>
          <FadeUp delay={0} className="mb-8 inline-flex items-center gap-2.5 border border-border px-3 py-1.5 readout text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] text-foreground-dim">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(74,222,128,0.9)]" />
            Race engineer system online
          </FadeUp>

          <FadeUp delay={0.08}>
            <h1 className="display mb-6 text-[length:var(--text-display)] leading-[0.95] text-foreground">
              Every pit call, cited.
            </h1>
          </FadeUp>

          <FadeUp delay={0.16}>
            <p className="mb-10 max-w-xl text-[length:var(--text-body)] leading-7 text-foreground-dim">
              A multi-agent F1 race engineer that reads telemetry, weighs regulations, and explains its
              calls. <span className="text-foreground">{evalStatus.passing}/{evalStatus.total}</span> fixtures
              passing, every recommendation cited — built up from a 40% baseline.
            </p>
          </FadeUp>

          <FadeUp delay={0.22} className="flex flex-wrap items-center gap-3">
            <Link href="/mission-control" className="btn btn--invert">
              Enter Mission Control →
            </Link>
            <Link
              href="#eval-arc"
              className="readout text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-dim transition-colors hover:text-foreground"
            >
              See how →
            </Link>
          </FadeUp>

          <div className="mt-12 grid grid-cols-3 gap-4">
            {heroStats.map((s, i) => (
              <FadeUp key={s.label} delay={0.3 + i * 0.08} className="divider pt-4">
                <p className="display mb-1 text-[length:var(--text-h2)] text-foreground">{s.value}</p>
                <p className="label">{s.label}</p>
                <p className="readout mt-1 text-[length:var(--text-readout)] text-foreground-faint">{s.hint}</p>
              </FadeUp>
            ))}
          </div>
        </div>

        {/* Right column — strategy preview card */}
        <motion.div
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.28, duration: 0.65, ease: [0.22, 0.61, 0.36, 1] }}
          className="card card--elevated space-y-4 p-6"
        >
          <div className="flex items-center justify-between border-b border-border pb-4">
            <div>
              <p className="label mb-1">Strategy Core</p>
              <p className="text-[length:var(--text-small)] font-semibold text-foreground">
                Japanese GP {"//"} Race {"//"} NOR
              </p>
            </div>
            <span className="readout border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 text-[0.55rem] uppercase tracking-[var(--track-wide)] text-emerald-400">
              Cited · 3 sources
            </span>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.55, duration: 0.4, ease: [0.22, 0.61, 0.36, 1] }}
            className="border border-accent-dim bg-accent-dim p-4"
          >
            <p className="label mb-1 text-foreground">Strategy Alert</p>
            <p className="mb-1.5 text-[length:var(--text-body)] font-bold text-foreground">
              Pit window opens in 4 laps.
            </p>
            <p className="readout text-[length:var(--text-readout)] leading-5 text-foreground-dim">
              Medium compound degradation crossing the threshold where undercut exposure becomes material.
            </p>
          </motion.div>

          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Tyre delta",    value: "+0.31s/lap" },
              { label: "Undercut risk", value: "High" },
              { label: "Traffic loss",  value: "1.8s" },
              { label: "Confidence",    value: "74%" },
            ].map(({ label, value }, i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.55 + i * 0.07, duration: 0.35, ease: [0.22, 0.61, 0.36, 1] }}
                className="border border-border p-3"
              >
                <p className="label mb-1">{label}</p>
                <p className="readout text-[length:var(--text-small)] font-semibold text-foreground">{value}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
        transition={{ delay: 0.85, duration: 0.6, ease: [0.22, 0.61, 0.36, 1] }}
        className="mt-14"
      >
        <TelemetryRibbon />
      </motion.div>
    </section>
  );
}

const ribbonItems = [
  "SECTOR 1 +0.184",
  "SECTOR 2 −0.092",
  "TYRE MEDIUM",
  "DRS ENABLED",
  "PACE DELTA −0.31",
  "PIT WINDOW LAP 18–22",
  "UNDERCUT RISK HIGH",
  "BATTERY DEPLOY PUSH",
  "GAP TO LEADER 3.4s",
  "STINT LENGTH 22 LAPS",
];

function TelemetryRibbon() {
  const doubled = [...ribbonItems, ...ribbonItems];
  return (
    <div className="telemetry-ribbon relative overflow-hidden border-y border-border py-2.5">
      <div className="telemetry-ribbon__track flex min-w-max items-center gap-10 px-6">
        {doubled.map((item, idx) => (
          <div key={idx} className="flex shrink-0 items-center gap-3">
            <span className="h-1 w-1 rounded-full bg-foreground-dim" />
            <span className="readout text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] text-foreground-dim">
              {item}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
