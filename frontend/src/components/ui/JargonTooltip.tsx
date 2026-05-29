"use client";

import { useId, useState } from "react";
import glossary from "@/content/glossary.json";

interface JargonTooltipProps {
  term: string;
  children: React.ReactNode;
}

export function JargonTooltip({ term, children }: JargonTooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const definition = (glossary as Record<string, string>)[term.toLowerCase()];

  if (!definition) return <>{children}</>;

  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-describedby={open ? id : undefined}
        className="border-b border-dotted border-foreground-faint text-inherit hover:text-foreground focus-visible:text-foreground focus-visible:outline-none"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        {children}
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 border border-border bg-overlay p-3 normal-case text-[length:var(--text-small)] leading-snug tracking-normal text-foreground shadow-xl"
        >
          {definition}
        </span>
      )}
    </span>
  );
}
