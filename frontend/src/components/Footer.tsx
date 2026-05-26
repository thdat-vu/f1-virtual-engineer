import Link from "next/link";

const GITHUB_URL = "https://github.com/thdat-vu/f1-virtual-engineer";
const LICENSE_URL = `${GITHUB_URL}/blob/main/LICENSE`;

// Standard footer for full-height pages (landing). Mission Control has its
// own fixed-height MissionFooter with telemetry stats and surfaces the
// attribution inline there instead — adding a second row would break the
// h-screen layout. See #231.
export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="readout text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground-faint">
          © {year} Vu Thanh Dat (ヴ・タイン・ダット)
        </p>
        <nav className="flex items-center gap-5 text-[0.55rem] uppercase tracking-[var(--track-wide)] text-foreground-faint">
          <Link
            href={LICENSE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="readout transition-colors hover:text-foreground"
          >
            MIT License
          </Link>
          <Link
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="readout flex items-center gap-1.5 transition-colors hover:text-foreground"
            aria-label="View source on GitHub"
          >
            <svg
              viewBox="0 0 24 24"
              width={12}
              height={12}
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.27-.01-1-.02-1.96-3.2.69-3.87-1.54-3.87-1.54-.52-1.32-1.27-1.67-1.27-1.67-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.69 1.24 3.35.95.1-.74.4-1.24.72-1.53-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.18-3.09-.12-.29-.51-1.46.11-3.05 0 0 .96-.31 3.15 1.18a10.96 10.96 0 0 1 5.74 0c2.19-1.49 3.15-1.18 3.15-1.18.62 1.59.23 2.76.11 3.05.74.8 1.18 1.83 1.18 3.09 0 4.42-2.69 5.39-5.25 5.68.41.35.78 1.04.78 2.1 0 1.52-.01 2.74-.01 3.11 0 .31.21.68.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z" />
            </svg>
            GitHub
          </Link>
        </nav>
      </div>
    </footer>
  );
}
