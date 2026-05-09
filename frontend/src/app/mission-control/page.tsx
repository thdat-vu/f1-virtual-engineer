"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { analyzeTelemetry, getEventDrivers, getEventsByYear } from "@/services/api";
import type { AnalyzeResponse, EventInfo } from "@/services/api";
import { useMissionStore } from "@/lib/store";
import { TeamIcon } from "@/components/icons/TeamIcons";

/* ─── Constants ─────────────────────────────────────────────── */
const TEAMS = [
  { id: "ferrari",     color: "#DC0000", label: "Ferrari" },
  { id: "redbull",     color: "#1E2A78", label: "Red Bull" },
  { id: "mercedes",    color: "#00D2BE", label: "Mercedes" },
  { id: "mclaren",     color: "#FF8700", label: "McLaren" },
  { id: "alpine",      color: "#1F5EFF", label: "Alpine" },
  { id: "astonmartin", color: "#006F62", label: "Aston Martin" },
  { id: "williams",    color: "#005AFF", label: "Williams" },
  { id: "haas",        color: "#B6BABD", label: "Haas" },
  { id: "rb",          color: "#6692FF", label: "Racing Bulls" },
  { id: "audi",        color: "#C8C8C8", label: "Revolut Audi" },
  { id: "cadillac",    color: "#D4AF37", label: "Cadillac" },
] as const;
type TeamId = (typeof TEAMS)[number]["id"];

const YEARS = [2024, 2023, 2022, 2021, 2020, 2019, 2018] as const;

const SESSIONS = [
  { id: "R",   label: "Race" },
  { id: "Q",   label: "Qualifying" },
  { id: "FP3", label: "FP3" },
  { id: "FP2", label: "FP2" },
  { id: "FP1", label: "FP1" },
] as const;
type SessionId = (typeof SESSIONS)[number]["id"];

const FALLBACK_DRIVERS = [
  "VER", "HAM", "LEC", "NOR", "SAI", "RUS", "PIA", "ALO",
  "STR", "PER", "GAS", "OCO", "TSU", "ALB", "HUL", "MAG",
  "BOT", "ZHO", "SAR", "RIC",
] as const;

const HOME_ICON_D = "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z";
const TELEMETRY_ICON_D = "M3 3v18h18M7 16l4-4 4 4 5-8";

/* ─── Small components ───────────────────────────────────────── */
function NavIcon({ d }: { d: string }) {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

function VDivider({ height = 5 }: { height?: number }) {
  return <div className="w-px shrink-0 bg-border" style={{ height: `${height * 0.25}rem` }} />;
}

function Select<T extends string>({
  value, onChange, options, loading, placeholder,
}: {
  value: T | "";
  onChange: (v: T) => void;
  options: { id: T; label: string }[];
  loading?: boolean;
  placeholder: string;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        disabled={loading}
        className="readout cursor-pointer appearance-none border border-border bg-surface-elevated pl-3 pr-7 py-1.5 text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] outline-none transition-colors focus:border-accent disabled:opacity-40"
        style={{
          color: value ? "var(--foreground)" : "var(--foreground-dim)",
          minWidth: "9rem",
        }}
      >
        <option value="" disabled>{loading ? "Loading…" : placeholder}</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>{o.label}</option>
        ))}
      </select>
      <svg width="8" height="8" viewBox="0 0 8 8" fill="none"
        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 opacity-50">
        <path d="M1 3l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    </div>
  );
}

/* ─── Chart builds a readable curve from min/avg/max ────────── */
function buildPath(min: number, avg: number, max: number): string {
  const vbH = 80;
  const norm = (v: number, lo: number, hi: number) =>
    hi === lo ? vbH / 2 : vbH - ((v - lo) / (hi - lo)) * vbH * 0.85 - vbH * 0.075;

  const lo = min * 0.95;
  const hi = max * 1.05;
  const yMin = norm(min, lo, hi);
  const yAvg = norm(avg, lo, hi);
  const yMax = norm(max, lo, hi);

  return [
    `M0 ${yMin.toFixed(1)}`,
    `C100 ${yMin.toFixed(1)} 180 ${yMax.toFixed(1)} 300 ${yMax.toFixed(1)}`,
    `C420 ${yMax.toFixed(1)} 500 ${yAvg.toFixed(1)} 650 ${yAvg.toFixed(1)}`,
    `C800 ${yAvg.toFixed(1)} 900 ${yMin.toFixed(1)} 1000 ${(yMin + 4).toFixed(1)}`,
  ].join(" ");
}

function TelemetryChart({
  label, unit, channelData, isLoading, hasData, animateKey,
}: {
  label: string; unit: string;
  channelData?: { min: number; max: number; avg: number } | null;
  isLoading: boolean; hasData: boolean; animateKey: number;
}) {
  const pathRef = useRef<SVGPathElement>(null);
  const pathD = channelData ? buildPath(channelData.min, channelData.avg, channelData.max) : "";

  useEffect(() => {
    if (!pathRef.current || !hasData || !pathD) return;
    const len = pathRef.current.getTotalLength();
    pathRef.current.style.strokeDasharray = `${len}`;
    pathRef.current.style.strokeDashoffset = `${len}`;
    const anim = pathRef.current.animate(
      [{ strokeDashoffset: len }, { strokeDashoffset: 0 }],
      { duration: 900, easing: "cubic-bezier(0.22,1,0.36,1)", fill: "forwards" },
    );
    return () => anim.cancel();
  }, [hasData, animateKey, pathD]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mb-2 flex shrink-0 items-baseline justify-between">
        <span className="label">{label}</span>
        <AnimatePresence mode="wait">
          {hasData && channelData ? (
            <motion.div key="value" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-baseline gap-3">
              <span className="readout text-[0.55rem] text-foreground-faint">
                {channelData.min.toFixed(0)} <span className="text-foreground-dim">min</span>
              </span>
              <span className="readout text-lg font-semibold text-foreground">
                {channelData.avg.toFixed(0)}
              </span>
              <span className="readout text-[0.55rem] text-foreground-faint">
                {channelData.max.toFixed(0)} <span className="text-foreground-dim">max</span>
              </span>
              <span className="label text-foreground-faint">{unit}</span>
            </motion.div>
          ) : (
            <motion.span key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="label text-foreground-faint">
              no data
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden border border-border bg-surface">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <motion.div className="h-px w-10 bg-accent"
              animate={{ scaleX: [1, 2.5, 1], opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
        )}

        {!isLoading && !hasData && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="readout text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-faint">
              Select session above and run analysis
            </span>
          </div>
        )}

        {!isLoading && hasData && pathD && (
          <svg className="h-full w-full" viewBox="0 0 1000 80" preserveAspectRatio="none">
            <path ref={pathRef} d={pathD} fill="none" stroke="var(--accent)" strokeWidth="1.4" />
          </svg>
        )}

        <div className="absolute inset-x-0 bottom-0 h-px bg-accent"
          style={{ opacity: hasData ? 0.2 : 0.06 }} />
      </div>
    </div>
  );
}

/* ─── Page ───────────────────────────────────────────────────── */
export default function MissionControlPage() {
  const { theme, setTheme, result, setResult, isLoading, setIsLoading } = useMissionStore();

  const [year, setYear]       = useState<number>(2024);
  const [eventName, setEvent] = useState<string>("");
  const [session, setSession] = useState<SessionId>("R");
  const [driver, setDriver]   = useState<string>("");

  const [events, setEvents]               = useState<EventInfo[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  const [fetchedDrivers, setFetchedDrivers] = useState<readonly string[] | null>(null);
  const [driversLoading, setDriversLoading] = useState(false);
  const [driversFallback, setDriversFallback] = useState(false);

  const drivers: readonly string[] =
    eventName && fetchedDrivers && fetchedDrivers.length > 0 ? fetchedDrivers : FALLBACK_DRIVERS;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    getEventsByYear(year)
      .then((res) => {
        if (!cancelled) {
          setEvents(res.events ?? []);
          setEvent("");
          setEventsLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setEvents([]);
          setEventsLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [year]);

  // Load real driver roster when an event is picked; fall back to the static
  // list if the backend returns an empty roster (event not raced yet, etc).
  useEffect(() => {
    if (!eventName) return;
    let cancelled = false;
    getEventDrivers(year, eventName)
      .then((res) => {
        if (cancelled) return;
        if (res.drivers.length > 0) {
          setFetchedDrivers(res.drivers);
          setDriversFallback(res.fallback);
        } else {
          setFetchedDrivers(null);
          setDriversFallback(true);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setFetchedDrivers(null);
        setDriversFallback(true);
      })
      .finally(() => {
        if (!cancelled) setDriversLoading(false);
      });
    return () => { cancelled = true; };
  }, [year, eventName]);

  const canRun = !isLoading && !!eventName && !!driver;

  const handleAnalyze = useCallback(async () => {
    if (!canRun) return;
    setIsLoading(true);
    try {
      const res = await analyzeTelemetry({
        query: `Analyse ${driver} ${session} session at ${eventName} ${year}`,
        driver,
        session_info: { event: eventName, year, session_type: session },
      });
      setResult(res as AnalyzeResponse);
    } catch {
      /* silent — HUD shows fallback state */
    } finally {
      setIsLoading(false);
    }
  }, [canRun, driver, session, eventName, year, setIsLoading, setResult]);

  const tel     = result?.telemetry_data;
  const strat   = result?.strategy_data;
  const hasData = !isLoading && !!result;
  const animKey = result ? 1 : 0;

  const displayDriver = result?.intent?.driver ?? driver ?? "—";
  const displayEvent  = result?.intent?.event  ?? eventName ?? "—";

  const activeTeam = TEAMS.find((t) => t.id === theme) ?? TEAMS[0];

  const eventOptions   = events.map((e) => ({ id: e.name, label: e.name }));
  const sessionOptions = SESSIONS.map((s) => ({ id: s.id, label: s.label }));
  const driverOptions  = drivers.map((d) => ({ id: d, label: d }));

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">

      {/* ── Sidebar ── */}
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

      {/* ── Main ── */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">

        {/* Status bar */}
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface px-5">
          <span className="label shrink-0 text-[length:var(--text-readout)]">Mission Control</span>
          <div className="h-3 w-px shrink-0 bg-border-strong" />
          <span className="readout shrink-0 text-[length:var(--text-readout)] text-foreground-dim">
            {displayDriver} {"//"} {displayEvent}
          </span>
          <div className="flex-1" />

          {/* Team switcher */}
          <div className="flex items-center gap-1.5">
            {TEAMS.map((t) => {
              const active = theme === t.id;
              return (
                <button key={t.id} onClick={() => setTheme(t.id as TeamId)}
                  title={t.label}
                  className="shrink-0 rounded-sm transition-all duration-[var(--dur-fast)]"
                  style={{
                    opacity:       active ? 1 : 0.35,
                    transform:     active ? "scale(1.5)" : "scale(1)",
                    outline:       active ? `1.5px solid ${t.color}` : "none",
                    outlineOffset: "2px",
                  }}>
                  <TeamIcon id={t.id} size={24} />
                </button>
              );
            })}
          </div>
        </header>

        {/* Selector bar */}
        <div className="flex shrink-0 items-center gap-2 border-b border-border bg-surface-elevated px-5 py-2.5">
          <Select<string>
            value={String(year)}
            onChange={(v) => {
              setYear(Number(v));
              setDriver("");
              setFetchedDrivers(null);
              setDriversFallback(false);
            }}
            options={YEARS.map((y) => ({ id: String(y), label: String(y) }))}
            placeholder="Year"
          />
          <VDivider />

          <Select<string>
            value={eventName}
            onChange={(v) => {
              setEvent(v);
              setDriver("");
              setFetchedDrivers(null);
              setDriversFallback(false);
              setDriversLoading(!!v);
            }}
            options={eventOptions}
            loading={eventsLoading}
            placeholder="Grand Prix"
          />
          <VDivider />

          <Select<SessionId>
            value={session}
            onChange={(v) => setSession(v)}
            options={sessionOptions}
            placeholder="Session"
          />
          <VDivider />

          <Select<string>
            value={driver}
            onChange={(v) => setDriver(v)}
            options={driverOptions}
            loading={driversLoading}
            placeholder="Driver"
          />
          {driversFallback && eventName ? (
            <span className="label text-foreground-faint" title="Live roster unavailable; using fallback list.">
              est.
            </span>
          ) : null}

          <div className="flex-1" />

          <button
            onClick={handleAnalyze}
            disabled={!canRun}
            className="btn btn--accent shrink-0 disabled:cursor-not-allowed disabled:opacity-30"
          >
            {isLoading ? "Computing…" : "Analyze"}
          </button>
        </div>

        {/* Telemetry canvas */}
        <div className="flex min-h-0 flex-1 flex-col gap-0 px-6 py-4">
          {(["Speed", "Throttle", "Brake"] as const).map((label, i) => {
            const ch = label === "Speed"    ? tel?.speed
                     : label === "Throttle" ? tel?.throttle
                     :                        tel?.brake;
            return (
              <div key={label} className={`min-h-0 flex-1 ${i > 0 ? "mt-3" : ""}`}>
                <TelemetryChart
                  label={label}
                  unit={label === "Speed" ? "KPH" : label === "Throttle" ? "%" : "BAR"}
                  channelData={ch}
                  isLoading={isLoading}
                  hasData={hasData}
                  animateKey={animKey}
                />
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <footer className="flex h-9 shrink-0 items-center gap-5 overflow-hidden border-t border-border bg-surface px-6">
          {[
            { label: "RPM",  value: tel?.rpm    ? `${tel.rpm.avg.toFixed(0)} avg`  : "—" },
            { label: "Gear", value: tel?.gear   ? `${tel.gear.avg.toFixed(1)} avg` : "—" },
            { label: "Pts",  value: tel?.sample_points ? `${tel.sample_points} samples` : "—" },
          ].map(({ label, value }, i) => (
            <div key={label} className="flex items-center gap-2">
              {i > 0 && <div className="h-3 w-px bg-border" />}
              <span className="label">{label}</span>
              <span className="readout text-[length:var(--text-readout)] text-foreground">{value}</span>
            </div>
          ))}
          <div className="ml-auto readout text-[length:var(--text-readout)] text-accent">
            {hasData && strat?.undercut_risk === "high" ? "HIGH UNDERCUT RISK" : hasData ? "ANALYSIS COMPLETE" : "AWAITING SESSION"}
          </div>
        </footer>
      </div>

      {/* ── Strategy HUD ── */}
      <aside className="flex w-72 shrink-0 flex-col border-l border-border bg-surface">

        <div className="shrink-0 border-b border-border px-5 pt-5 pb-4">
          <div className="mb-1 flex items-center gap-2">
            <p className="label">Strategy HUD</p>
            <TeamIcon id={activeTeam.id} size={14} />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="readout text-[length:var(--text-readout)] text-foreground-dim">
              {session} {"//"} {hasData && strat?.target_lap ? `PIT LAP ${strat.target_lap}` : "NO DATA"}
            </span>
            <span className="readout text-[length:var(--text-readout)] text-foreground-dim">
              {hasData && strat?.confidence_band ? strat.confidence_band.toUpperCase() : "—"}
            </span>
          </div>
        </div>

        <div className="mx-4 mt-4 shrink-0 border border-accent-dim bg-accent-dim p-4">
          <p className="label mb-2 text-accent">
            {hasData && strat?.undercut_risk === "high" ? "⚠ STRATEGY ALERT" : "SYSTEM STATUS"}
          </p>
          <p className="readout text-[0.7rem] font-semibold uppercase leading-snug text-foreground">
            {isLoading
              ? "Fetching telemetry…"
              : hasData
                ? (result?.agent_response ?? "Analysis complete.")
                : "Select year, grand prix, session and driver above."}
          </p>
        </div>

        <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-4">
          <p className="label mb-3">Tactical Rationale</p>
          <AnimatePresence mode="wait">
            <motion.ul key={hasData ? "data" : "idle"} className="space-y-2">
              {(hasData && strat?.rationale?.length
                ? strat.rationale
                : [
                    "Awaiting session selection.",
                    "Tyre degradation model ready.",
                    "Pace delta tracking idle.",
                    "Competitor windows standby.",
                  ]
              ).map((line, i) => (
                <motion.li key={i}
                  initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.07, duration: 0.3 }}
                  className="readout flex gap-2 text-[length:var(--text-readout)] text-foreground-dim">
                  <span className="text-accent">—</span>
                  <span>{line}</span>
                </motion.li>
              ))}
            </motion.ul>
          </AnimatePresence>

          {hasData && strat?.recommended_pit_window_laps?.length === 2 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="mb-4 mt-4 border border-border p-3">
              <p className="label mb-1">Pit Window</p>
              <p className="readout text-base font-bold text-accent">
                LAP {strat.recommended_pit_window_laps[0]} – {strat.recommended_pit_window_laps[1]}
              </p>
              {strat.fallback && (
                <p className="readout mt-1 text-[0.55rem] text-foreground-faint">
                  {strat.fallback_reason ?? "Estimate — live data unavailable"}
                </p>
              )}
            </motion.div>
          )}
        </div>
      </aside>
    </div>
  );
}
