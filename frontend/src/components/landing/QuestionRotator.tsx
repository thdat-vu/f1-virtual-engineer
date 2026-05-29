"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

const SUZUKA_R = "/mission-control?event=Japanese%20Grand%20Prix&session=R";

const QUESTIONS: ReadonlyArray<{ text: string; href: string }> = [
  { text: "How fast was VER's fastest lap at Suzuka?", href: `${SUZUKA_R}&driver=VER&lap=fastest` },
  { text: "Where did HAM gain time on VER?",          href: `${SUZUKA_R}&driver=HAM&lap=fastest` },
  { text: "What set LEC's pace through the esses?",   href: `${SUZUKA_R}&driver=LEC&lap=fastest` },
  { text: "When did the pit window open for NOR?",    href: `${SUZUKA_R}&driver=NOR&lap=fastest` },
];

const ROTATE_MS = 3500;

export function QuestionRotator() {
  const reduced = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (reduced || paused) return;
    const id = window.setInterval(
      () => setIndex((n) => (n + 1) % QUESTIONS.length),
      ROTATE_MS,
    );
    return () => window.clearInterval(id);
  }, [reduced, paused]);

  const q = QUESTIONS[index];

  return (
    <div
      className="mb-8 min-h-[1.75rem]"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={index}
          initial={reduced ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduced ? undefined : { opacity: 0, y: -6 }}
          transition={{ duration: 0.3, ease: [0.22, 0.61, 0.36, 1] }}
        >
          <Link
            href={q.href}
            className="readout inline-flex items-center gap-2 text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-dim transition-colors hover:text-foreground"
          >
            <span aria-hidden>→</span>
            {q.text}
          </Link>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
