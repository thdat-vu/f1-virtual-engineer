"use client";

import { motion, useReducedMotion } from "framer-motion";

interface StartingGridLoaderProps {
  label?: string;
}

const DOT_COUNT = 5;

export function StartingGridLoader({ label = "LIGHTS OUT" }: StartingGridLoaderProps) {
  const reduced = useReducedMotion();

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={label.toLowerCase()}
      className="flex flex-col items-center gap-2"
    >
      <div className="flex gap-1.5">
        {Array.from({ length: DOT_COUNT }).map((_, i) =>
          reduced ? (
            <span
              key={i}
              className="h-2 w-2 rounded-full bg-foreground-faint"
              aria-hidden
            />
          ) : (
            <motion.span
              key={i}
              aria-hidden
              className="h-2 w-2 rounded-full bg-foreground-faint"
              animate={{
                backgroundColor: [
                  "var(--foreground-faint, rgba(255,255,255,0.2))",
                  "rgb(239 68 68)",
                  "var(--foreground-faint, rgba(255,255,255,0.2))",
                ],
              }}
              transition={{
                duration: 1.4,
                repeat: Infinity,
                ease: "easeInOut",
                delay: i * 0.18,
              }}
            />
          ),
        )}
      </div>
      <span className="readout text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground-faint">
        {label}
      </span>
    </div>
  );
}
