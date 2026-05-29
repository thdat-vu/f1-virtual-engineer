"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type NavItem = { label: string; href: string };

// Items whose href is "#section" participate in scroll-spy. External
// hrefs (e.g. /mission-control) are excluded — they navigate away.
export function LandingNav({ items }: { items: readonly NavItem[] }) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const sectionIds = items
      .filter((i) => i.href.startsWith("#"))
      .map((i) => i.href.slice(1));
    const sections = sectionIds
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => Boolean(el));

    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) {
          setActive(`#${(visible[0].target as HTMLElement).id}`);
        }
      },
      {
        rootMargin: "-20% 0px -50% 0px",
        threshold: [0, 0.25, 0.5, 1],
      },
    );

    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, [items]);

  return (
    <nav className="hidden items-center gap-8 md:flex">
      {items.map((item) => {
        const isActive = active === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive ? "true" : undefined}
            className={`readout text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] transition-colors ${
              isActive
                ? "text-foreground"
                : "text-foreground-dim hover:text-foreground"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
