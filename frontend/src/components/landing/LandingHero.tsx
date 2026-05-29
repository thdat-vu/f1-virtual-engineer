"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { QuestionRotator } from "@/components/landing/QuestionRotator";

const DEMO_HREF =
  "/mission-control?event=Japanese%20Grand%20Prix&session=R&driver=VER&lap=fastest";

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

export function LandingHero() {
  const heroStats = [
    { label: "Multi-agent",   value: "4 agents",  hint: "pit · tyre · weather · pace" },
    { label: "Every call",    value: "Cited",     hint: "linked to FastF1 + regs" },
    { label: "Any race",      value: "Live",      hint: "regenerates from lap data" },
  ];

  return (
    <section className="relative overflow-hidden pt-16 pb-20">
      <div className="hero-grid pointer-events-none absolute inset-0 opacity-40" />

      <div className="relative z-10 grid gap-14 lg:grid-cols-[1fr_460px] lg:items-center">
        {/* Left column — copy */}
        <div>
          <FadeUp delay={0} className="mb-8 inline-flex items-center gap-2.5 border border-border px-3 py-1.5 readout text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] text-foreground-dim">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(74,222,128,0.9)]" />
            Race engineer · in your browser
          </FadeUp>

          <FadeUp delay={0.08}>
            <h1 className="display mb-6 text-[length:var(--text-display)] leading-[0.95] text-foreground">
              Ask any lap.<br />Get the call.
            </h1>
          </FadeUp>

          <FadeUp delay={0.14}>
            <QuestionRotator />
          </FadeUp>

          <FadeUp delay={0.16}>
            <p className="mb-10 max-w-xl text-[length:var(--text-body)] leading-7 text-foreground-dim">
              Compare drivers, replay strategy, read every pit recommendation backed by FastF1
              telemetry and a regulation-aware corpus. <span className="text-foreground">No spreadsheets.</span>
            </p>
          </FadeUp>

          <FadeUp delay={0.22} className="flex flex-wrap items-center gap-3">
            <Link href={DEMO_HREF} className="btn btn--invert">
              Open Mission Control on Suzuka 2024 →
            </Link>
            <Link
              href="#capabilities"
              className="readout text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-dim transition-colors hover:text-foreground"
            >
              See a sample query →
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

        {/* Right column — animated lap-delta preview */}
        <motion.div
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.28, duration: 0.65, ease: [0.22, 0.61, 0.36, 1] }}
          className="card card--elevated space-y-4 p-6"
        >
          <div className="flex items-center justify-between border-b border-border pb-4">
            <div>
              <p className="label mb-1">Lap delta</p>
              <p className="text-[length:var(--text-small)] font-semibold text-foreground">
                Suzuka 2024 {"//"} Race {"//"} VER vs HAM
              </p>
            </div>
            <span className="readout border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 text-[0.55rem] uppercase tracking-[var(--track-wide)] text-emerald-400">
              Cited · 3 sources
            </span>
          </div>

          <LapDeltaPreview />

          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Sector 1", value: "+0.184" },
              { label: "Sector 2", value: "−0.092" },
              { label: "Sector 3", value: "+0.221" },
              { label: "Lap delta", value: "+0.31s" },
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

// Synthetic-but-plausible lap-delta curve illustrating VER vs HAM at
// Suzuka. Real values would come from /lap-delta — these points exist
// only to make the hero card feel alive on first paint, never quoted
// as data anywhere downstream.
const DELTA_POINTS = [
  0.00, 0.04, 0.09, 0.18, 0.22, 0.19, 0.11, 0.02,
  -0.06, -0.14, -0.21, -0.18, -0.09, 0.04, 0.13, 0.21,
  0.27, 0.31, 0.28, 0.22, 0.17, 0.14, 0.18, 0.24,
  0.31,
];

function LapDeltaPreview() {
  const W = 380;
  const H = 120;
  const PAD_X = 8;
  const PAD_Y = 12;

  const xs = DELTA_POINTS.map(
    (_, i) => PAD_X + (i / (DELTA_POINTS.length - 1)) * (W - PAD_X * 2),
  );
  const max = Math.max(...DELTA_POINTS.map(Math.abs));
  const ys = DELTA_POINTS.map(
    (v) => H / 2 - (v / max) * (H / 2 - PAD_Y),
  );
  const path = xs.map((x, i) => `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" ");

  return (
    <div className="relative border border-border bg-surface">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-[120px] w-full" aria-hidden>
        <line
          x1={PAD_X}
          x2={W - PAD_X}
          y1={H / 2}
          y2={H / 2}
          stroke="currentColor"
          strokeOpacity={0.12}
          strokeDasharray="2 4"
        />
        <text
          x={PAD_X}
          y={H / 2 - 4}
          fontSize={8}
          fill="currentColor"
          fillOpacity={0.35}
          fontFamily="ui-monospace,SFMono-Regular,monospace"
        >
          Δt = 0
        </text>

        <motion.path
          d={path}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={1.6}
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ delay: 0.6, duration: 1.6, ease: [0.22, 0.61, 0.36, 1] }}
        />

        <motion.circle
          r={3}
          fill="var(--accent)"
          initial={{ opacity: 0 }}
          animate={{
            opacity: [0, 1, 1, 0],
            cx: [xs[0], xs[Math.floor(xs.length / 2)], xs[xs.length - 1], xs[xs.length - 1]],
            cy: [ys[0], ys[Math.floor(ys.length / 2)], ys[ys.length - 1], ys[ys.length - 1]],
          }}
          transition={{ delay: 0.6, duration: 1.6, ease: "linear", times: [0, 0.5, 1, 1] }}
        />
      </svg>

      <div className="flex items-center justify-between border-t border-border px-3 py-1.5">
        <span className="readout text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground-faint">
          T1 → finish
        </span>
        <span className="readout text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground-dim">
          VER ahead by 0.31s
        </span>
      </div>
    </div>
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
