"use client";

import Link from "next/link";
import { NavIcon } from "./primitives";
import { HOME_ICON_D, TELEMETRY_ICON_D } from "./constants";

export function NavRail() {
  return (
    <nav className="z-40 flex w-14 shrink-0 flex-col items-center gap-0 border-r border-border bg-surface py-5">
      <div className="mb-8 flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-accent text-[0.85rem] font-black italic text-background">
        A
      </div>
      <div className="flex flex-col items-center gap-5">
        <Link href="/" title="Landing" className="rounded p-1 text-foreground-dim transition-colors hover:text-foreground">
          <NavIcon d={HOME_ICON_D} />
        </Link>
        <span title="Telemetry (current view)" aria-current="page" className="rounded p-1 text-accent">
          <NavIcon d={TELEMETRY_ICON_D} />
        </span>
      </div>
    </nav>
  );
}
