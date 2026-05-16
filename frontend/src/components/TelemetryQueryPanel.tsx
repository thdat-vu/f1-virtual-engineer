"use client";

import { AnimatePresence, motion } from "framer-motion";
import { 
  Activity, 
  ChevronRight, 
  HelpCircle, 
  Info, 
  Zap, 
  Target, 
  TrendingUp,
  X
} from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";

import { analyzeTelemetry, AnalyzeResponse, StrategyData, getEventsByYear, EventInfo } from "@/services/api";

const DRIVER_OPTIONS = [
  { code: "VER", label: "Max Verstappen" },
  { code: "HAM", label: "Lewis Hamilton" },
  { code: "NOR", label: "Lando Norris" },
  { code: "LEC", label: "Charles Leclerc" },
  { code: "SAI", label: "Carlos Sainz" },
  { code: "RUS", label: "George Russell" },
  { code: "PIA", label: "Oscar Piastri" },
  { code: "PER", label: "Sergio Perez" },
  { code: "ALO", label: "Fernando Alonso" },
  { code: "STR", label: "Lance Stroll" },
  { code: "TSU", label: "Yuki Tsunoda" },
  { code: "ALB", label: "Alexander Albon" },
  { code: "GAS", label: "Pierre Gasly" },
  { code: "OCO", label: "Esteban Ocon" },
  { code: "HUL", label: "Nico Hulkenberg" },
  { code: "MAG", label: "Kevin Magnussen" },
  { code: "BOT", label: "Valtteri Bottas" },
  { code: "ZHO", label: "Guanyu Zhou" },
  { code: "RIC", label: "Daniel Ricciardo" },
  { code: "BEA", label: "Oliver Bearman" },
];

const YEAR_OPTIONS = [2023, 2024, 2025];

const SESSION_OPTIONS = [
  { value: "FP1", label: "Practice 1" },
  { value: "Q", label: "Qualifying" },
  { value: "R", label: "Race" },
];

interface TelemetryQueryPanelProps {
  variant?: "preview" | "dashboard";
}

export function TelemetryQueryPanel({
  variant = "preview",
}: TelemetryQueryPanelProps) {
  const [driver, setDriver] = useState("VER");
  const [eventName, setEventName] = useState("Japanese Grand Prix");
  const [year, setYear] = useState(2023);
  const [sessionType, setSessionType] = useState("R");
  const [availableEvents, setAvailableEvents] = useState<EventInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingEvents, setIsFetchingEvents] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [showTutorial, setShowTutorial] = useState(false);

  useEffect(() => {
    async function fetchEvents() {
      setIsFetchingEvents(true);
      try {
        const response = await getEventsByYear(year);
        if (response.status === "success") {
          setAvailableEvents(response.events);
          // If current event is not in new list, reset to first event
          if (response.events.length > 0 && !response.events.some(e => e.name === eventName)) {
            setEventName(response.events[0].name);
          }
        }
      } catch (err) {
        console.error("Failed to fetch events:", err);
      } finally {
        setIsFetchingEvents(false);
      }
    }
    fetchEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year]);

  useEffect(() => {
    const hasSeenTutorial = localStorage.getItem("apex-tutorial-seen");
    if (!hasSeenTutorial) {
      // Defer to avoid synchronous setState warning in effect
      const timeout = setTimeout(() => setShowTutorial(true), 100);
      return () => clearTimeout(timeout);
    }
  }, []);

  const closeTutorial = () => {
    setShowTutorial(false);
    localStorage.setItem("apex-tutorial-seen", "true");
  };

  const isDashboard = variant === "dashboard";

  const statusTag = useMemo(() => {
    if (isLoading || isFetchingEvents) {
      return "LOADING";
    }
    if (errorMessage) {
      return "ERROR";
    }
    if (result) {
      return "READY";
    }
    return "IDLE";
  }, [errorMessage, isLoading, result, isFetchingEvents]);

  const driverLabel =
    DRIVER_OPTIONS.find((option) => option.code === driver)?.label ?? driver;
  const eventLabel =
    availableEvents.find((e) => e.name === eventName)?.name ?? eventName;
  const sessionLabel =
    SESSION_OPTIONS.find((option) => option.value === sessionType)?.label ??
    sessionType;

  const strategySignals = useMemo(() => {
    const strategy = result?.strategy_data;
    const speedAvg = result?.telemetry_data?.speed?.avg;
    const gearAvg = result?.telemetry_data?.gear?.avg;
    const fallback = strategy?.fallback ?? result?.telemetry_data?.fallback;
    const samplePoints = result?.telemetry_data?.sample_points;

    const paceProfile =
      speedAvg == null
        ? strategy?.confidence_band
          ? `Strategy-led / ${strategy.confidence_band} confidence`
          : "Awaiting telemetry"
        : speedAvg >= 235
          ? "High-speed stable"
          : speedAvg >= 210
            ? "Balanced race pace"
            : "Traffic-sensitive pace";

    const strategyBias = strategy
      ? `${capitalize(strategy.undercut_risk)} undercut risk`
      : speedAvg == null
        ? "Need a fresh query"
        : speedAvg >= 230
          ? "Favors attack / undercut pressure"
          : speedAvg >= 215
            ? "Neutral, monitor tyre decay"
            : "Protect track position first";

    const evidenceQuality = strategy
      ? strategy.fallback
        ? "Recommendation unavailable"
        : strategy.assumptions.length > 0
          ? "Explainable heuristic"
          : "Thin strategy evidence"
      : samplePoints == null
        ? "No telemetry snapshot yet"
        : samplePoints >= 100
          ? "Strong evidence"
          : samplePoints >= 50
            ? "Usable evidence"
            : "Thin evidence";

    const confidence = fallback
      ? "Lower confidence"
      : strategy?.confidence_band
        ? `${capitalize(strategy.confidence_band)} confidence`
        : samplePoints == null
          ? "Waiting"
          : samplePoints >= 100
            ? "High confidence"
            : "Medium confidence";

    const drivability =
      gearAvg == null
        ? strategy?.rationale?.[0] ?? "Unknown"
        : gearAvg >= 6
          ? "Flowing high-gear sections"
          : gearAvg >= 4.5
            ? "Mixed-speed track"
            : "Low-speed traction heavy";

    return {
      paceProfile,
      strategyBias,
      evidenceQuality,
      confidence,
      drivability,
    };
  }, [result]);

  async function handleAction(intent: "telemetry" | "strategy") {
    setIsLoading(true);
    setErrorMessage(null);

    const query = intent === "strategy" 
      ? `Predict strategy and pit window for ${driver}` 
      : `Show telemetry pace for ${driver}`;

    try {
      const response = await analyzeTelemetry({
        query,
        driver,
        session_info: {
          event: eventName,
          year,
          session_type: sessionType,
        },
      });
      setResult(response);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown request error.";
      setErrorMessage(message);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  }

  if (!isDashboard) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 hover:border-red-900/50 transition-colors">
        <div className="flex flex-col gap-3 border-b border-white/10 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400">
              Live Telemetry Query
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              A compact preview of the real mission-control loop.
            </p>
          </div>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-[10px] font-mono uppercase tracking-[0.3em] text-slate-300">
            Status: {statusTag}
          </span>
        </div>

        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <select
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
              className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-3 text-xs text-slate-100 outline-none transition focus:border-red-500/50"
            >
              {YEAR_OPTIONS.map((y) => (
                <option key={y} value={y}>
                  {y} Season
                </option>
              ))}
            </select>
            <select
              value={eventName}
              onChange={(event) => setEventName(event.target.value)}
              className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-3 text-xs text-slate-100 outline-none transition focus:border-red-500/50"
              disabled={isFetchingEvents}
            >
              {availableEvents.map((event) => (
                <option key={event.round} value={event.name}>
                  {event.name}
                </option>
              ))}
            </select>
            <select
              value={driver}
              onChange={(event) => setDriver(event.target.value)}
              className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-3 text-xs text-slate-100 outline-none transition focus:border-red-500/50"
            >
              {DRIVER_OPTIONS.map((option) => (
                <option key={option.code} value={option.code}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleAction("telemetry")}
              disabled={isLoading || isFetchingEvents}
              className="flex-1 rounded-xl bg-slate-800 border border-slate-700 px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-white transition hover:bg-slate-700 disabled:opacity-50"
            >
              Pace Analysis
            </button>
            <button
              onClick={() => handleAction("strategy")}
              disabled={isLoading || isFetchingEvents}
              className="flex-1 rounded-xl bg-red-700 px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-white transition hover:bg-red-600 disabled:opacity-50"
            >
              Pit Strategy
            </button>
          </div>
        </div>

        <div className="mt-6 min-h-48 rounded-xl border border-dashed border-slate-800 bg-slate-950/50 p-4">
          {isLoading && (
            <p className="text-sm font-mono text-slate-400">
              Running query against backend agent...
            </p>
          )}

          {!isLoading && errorMessage && (
            <div className="rounded-xl border border-red-900/40 bg-red-950/30 p-3">
              <p className="text-xs font-bold uppercase text-red-400">Request error</p>
              <p className="mt-2 text-sm text-slate-200">{errorMessage}</p>
            </div>
          )}

          {!isLoading && !errorMessage && result && (
            <div className="space-y-3">
              <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-3">
                <p className="text-xs font-bold uppercase text-slate-400">Agent response</p>
                <p className="mt-2 text-sm text-slate-100">{result.agent_response}</p>
              </div>
              {result.strategy_data && (
                <div className="grid grid-cols-1 gap-3 text-xs md:grid-cols-2">
                  <MetricCard title="Pit window" value={formatPitWindow(result.strategy_data)} />
                  <MetricCard title="Confidence" value={capitalize(result.strategy_data.confidence_band)} />
                </div>
              )}
              {result.telemetry_data?.speed && (
                <div className="grid grid-cols-1 gap-3 text-xs md:grid-cols-3">
                  <MetricCard title="Speed avg" value={formatChannel(result.telemetry_data.speed)} />
                  <MetricCard title="Gear avg" value={formatChannel(result.telemetry_data.gear)} />
                  <MetricCard title="RPM avg" value={formatChannel(result.telemetry_data.rpm, 0)} />
                </div>
              )}
            </div>
          )}

          {!isLoading && !errorMessage && !result && (
            <p className="text-sm font-mono uppercase text-slate-600">
              Submit a telemetry or strategy prompt to view results.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-[2rem] border border-white/10 bg-slate-950/85 p-6 shadow-[0_32px_64px_rgba(2,6,23,0.5)] backdrop-blur-xl">
      <div className="flex flex-col gap-4 border-b border-white/10 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-red-300">
            Mission control query
          </p>
          <h2 className="mt-2 text-xl font-bold uppercase tracking-[-0.04em] text-white sm:text-2xl">
            Run telemetry-backed strategy analysis
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Choose a race context, run a focused telemetry or strategy question, and inspect a baseline recommendation with explicit assumptions.
          </p>
        </div>
        <span className="h-fit rounded-full border border-white/10 bg-white/5 px-3 py-2 text-[10px] font-mono uppercase tracking-[0.3em] text-slate-300">
          Status: {statusTag}
        </span>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <ContextCard label="Driver" value={driver} detail={driverLabel} />
        <ContextCard label="Event" value={eventLabel} detail={eventName} />
        <ContextCard label="Year" value={String(year)} detail="Season" />
        <ContextCard label="Session" value={sessionType} detail={sessionLabel} />
        <ContextCard
          label="Mode"
          value={result?.intent?.intent_type === "strategy" ? "Strategy" : "Telemetry"}
          detail="Explainable AI"
        />
        <ContextCard label="Confidence" value={strategySignals.confidence} detail={statusTag} />
      </div>

      <div className="mt-6 space-y-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
          <Field label="Driver">
            <select
              value={driver}
              onChange={(event) => setDriver(event.target.value)}
              className="dashboard-input"
            >
              {DRIVER_OPTIONS.map((option) => (
                <option key={option.code} value={option.code}>
                  {option.label} ({option.code})
                </option>
              ))}
            </select>
          </Field>

          <Field label="Event">
            <select
              value={eventName}
              onChange={(event) => setEventName(event.target.value)}
              className="dashboard-input"
              disabled={isFetchingEvents}
            >
              {availableEvents.map((event) => (
                <option key={event.round} value={event.name}>
                  {event.name} ({event.location})
                </option>
              ))}
              {availableEvents.length === 0 && !isFetchingEvents && (
                <option value="">No events found</option>
              )}
              {isFetchingEvents && (
                <option value="">Loading events...</option>
              )}
            </select>
          </Field>

          <Field label="Year">
            <select
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
              className="dashboard-input"
            >
              {YEAR_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Session">
            <select
              value={sessionType}
              onChange={(event) => setSessionType(event.target.value)}
              className="dashboard-input"
            >
              {SESSION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between pt-2">
          <div className="flex flex-wrap gap-2">
            <ActionButton 
              onClick={() => handleAction("telemetry")}
              disabled={isLoading}
              icon={<TrendingUp className="w-4 h-4" />}
              label="Analyze Pace"
              sublabel="Telemetry Summary"
            />
            <ActionButton 
              onClick={() => handleAction("strategy")}
              disabled={isLoading}
              variant="accent"
              icon={<Target className="w-4 h-4" />}
              label="Predict Strategy"
              sublabel="Pit Window & Risk"
            />
            <button 
              onClick={() => setShowTutorial(true)}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-white/5 border border-white/10 px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-400 transition hover:bg-white/10"
            >
              <HelpCircle className="w-4 h-4" />
              How to use
            </button>
          </div>
          <p className="max-w-xs text-[10px] uppercase tracking-widest leading-relaxed text-slate-500">
            Select context, then choose an action. No manual prompting required.
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-slate-500">
                Response console
              </p>
              <p className="mt-2 text-sm text-slate-400">
                Baseline strategy recommendation, telemetry summary, and failure states all surface here.
              </p>
            </div>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-300">
              Live panel
            </span>
          </div>

          <div className="mt-5 min-h-72 rounded-[1.5rem] border border-dashed border-white/10 bg-slate-950/60 p-4">
            {isLoading && (
              <div className="space-y-4">
                <p className="text-sm font-mono text-slate-300">
                  Running query against backend agent...
                </p>
                <div className="space-y-3">
                  <LoadingBar width="75%" />
                  <LoadingBar width="52%" />
                  <LoadingBar width="66%" />
                </div>
              </div>
            )}

            {!isLoading && errorMessage && (
              <div className="rounded-[1.5rem] border border-red-500/30 bg-red-500/10 p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-red-300">
                  Request error
                </p>
                <p className="mt-3 text-sm text-slate-100">{errorMessage}</p>
                <p className="mt-3 text-sm leading-6 text-slate-400">
                  Action: verify the backend is running and make sure <code>NEXT_PUBLIC_API_BASE_URL</code> points to the API server.
                </p>
              </div>
            )}

            {!isLoading && !errorMessage && result && (
              <div className="space-y-4">
                <div className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-slate-400">
                    Agent response
                  </p>
                  <p className="mt-3 text-sm leading-7 text-slate-100">{result.agent_response}</p>
                </div>

                {result.strategy_data && (
                  <StrategyRecommendationBlock strategy={result.strategy_data} />
                )}

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <MetricCard title="Speed avg" value={formatChannel(result.telemetry_data?.speed)} />
                  <MetricCard title="Gear avg" value={formatChannel(result.telemetry_data?.gear)} />
                  <MetricCard title="RPM avg" value={formatChannel(result.telemetry_data?.rpm, 0)} />
                  <MetricCard
                    title="Sample points"
                    value={
                      result.telemetry_data?.sample_points
                        ? String(result.telemetry_data.sample_points)
                        : "N/A"
                    }
                  />
                  <MetricCard
                    title="Fallback"
                    value={result.strategy_data?.fallback || result.telemetry_data?.fallback ? "Yes" : "No"}
                  />
                  <MetricCard title="Intent driver" value={result.intent?.driver ?? driver} />
                </div>
              </div>
            )}

            {!isLoading && !errorMessage && !result && (
              <div className="flex min-h-60 flex-col justify-center items-center rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-8 text-center">
                <Activity className="w-12 h-12 text-slate-700 mb-4" />
                <h3 className="text-xl font-bold text-white">
                  Mission Control Ready
                </h3>
                <p className="mt-3 max-w-sm text-sm leading-7 text-slate-400">
                  Select a driver and event context above, then choose an analysis action to begin telemetry ingestion.
                </p>
              </div>
            )}
          </div>
        </div>

        <aside className="space-y-4">
          <PanelCard
            eyebrow="Selected context"
            title="Keep the race assumptions explicit."
            body="The more configurable this surface becomes, the more important it is to show users what exact race context is being analyzed."
          >
            <dl className="mt-5 space-y-3 text-sm text-slate-300">
              <ContextRow label="Driver" value={`${driverLabel} (${driver})`} />
              <ContextRow label="Event" value={eventName} />
              <ContextRow label="Year" value={String(year)} />
              <ContextRow label="Session" value={`${sessionLabel} (${sessionType})`} />
            </dl>
          </PanelCard>

          <PanelCard
            eyebrow="Strategy snapshot"
            title="Turn telemetry into a quick engineering read."
            body="These cards do not pretend to be race-team-grade simulation. They expose a heuristic read with visible assumptions and confidence."
          >
            <div className="mt-5 grid gap-3">
              <MiniSignalCard label="Pace profile" value={strategySignals.paceProfile} />
              <MiniSignalCard label="Strategy bias" value={strategySignals.strategyBias} />
              <MiniSignalCard label="Evidence quality" value={strategySignals.evidenceQuality} />
              <MiniSignalCard label="Drivability" value={strategySignals.drivability} />
            </div>
          </PanelCard>

          <PanelCard
            eyebrow="Operator checklist"
            title="What this slice improves"
            body="The dashboard now behaves more like a real operator surface and less like a fixed telemetry demo."
          >
            <ul className="mt-5 space-y-3 text-sm text-slate-300">
              <ChecklistItem text="Strategy questions now return a visible recommendation block." />
              <ChecklistItem text="Pit window, risk, confidence, assumptions, and rationale stay explicit." />
              <ChecklistItem text="Event, year, and session remain visible before and after every run." />
              <ChecklistItem text="Error and fallback states remain honest and actionable." />
            </ul>
          </PanelCard>
        </aside>
      </div>

      <AnimatePresence>
        {showTutorial && <TutorialOverlay onClose={closeTutorial} />}
      </AnimatePresence>
    </div>
  );
}

function ActionButton({ 
  onClick, 
  disabled, 
  icon, 
  label, 
  sublabel,
  variant = "default" 
}: { 
  onClick: () => void; 
  disabled: boolean; 
  icon: ReactNode; 
  label: string; 
  sublabel: string;
  variant?: "default" | "accent";
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        group relative flex items-center gap-4 rounded-2xl border px-5 py-4 transition-all
        ${variant === "accent" 
          ? "bg-red-700 border-red-600 hover:bg-red-600 shadow-[0_8px_16px_rgba(185,28,28,0.2)]" 
          : "bg-white/5 border-white/10 hover:bg-white/10"
        }
        disabled:opacity-50 disabled:cursor-not-allowed
      `}
    >
      <div className={`
        flex h-10 w-10 items-center justify-center rounded-xl transition-colors
        ${variant === "accent" ? "bg-white/10 text-white" : "bg-white/5 text-slate-400 group-hover:text-white"}
      `}>
        {icon}
      </div>
      <div className="text-left">
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white">
          {label}
        </p>
        <p className={`text-[10px] uppercase tracking-[0.1em] ${variant === "accent" ? "text-red-200" : "text-slate-500"}`}>
          {sublabel}
        </p>
      </div>
      <ChevronRight className={`w-4 h-4 ml-2 transition-transform group-hover:translate-x-1 ${variant === "accent" ? "text-white/50" : "text-slate-700"}`} />
    </button>
  );
}

function TutorialOverlay({ onClose }: { onClose: () => void }) {
  const steps = [
    {
      icon: <Activity className="w-6 h-6 text-red-500" />,
      title: "Select Context",
      description: "Pick your driver, event, and year from the mission control selectors."
    },
    {
      icon: <Zap className="w-6 h-6 text-red-500" />,
      title: "Choose Action",
      description: "Click an action button to run specialized telemetry or strategy analysis."
    },
    {
      icon: <Info className="w-6 h-6 text-red-500" />,
      title: "Inspect Results",
      description: "Review agent responses and explainable metrics in the console."
    }
  ];

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-6"
    >
      <motion.div 
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        className="relative max-w-2xl w-full rounded-[2.5rem] border border-white/10 bg-slate-900 p-8 shadow-2xl"
      >
        <button 
          onClick={onClose}
          className="absolute top-6 right-6 p-2 rounded-full bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center mb-10">
          <p className="text-[10px] font-bold uppercase tracking-[0.4em] text-red-500">
            System Orientation
          </p>
          <h2 className="mt-4 text-3xl font-bold text-white uppercase tracking-tight">
            How to operate the engineer
          </h2>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {steps.map((step, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.15 + 0.2 }}
              className="flex flex-col items-center text-center p-4"
            >
              <div className="mb-4 p-4 rounded-2xl bg-white/5">
                {step.icon}
              </div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                {step.title}
              </h3>
              <p className="mt-3 text-xs leading-relaxed text-slate-400">
                {step.description}
              </p>
            </motion.div>
          ))}
        </div>

        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="mt-12 flex justify-center"
        >
          <button 
            onClick={onClose}
            className="rounded-full bg-red-600 px-8 py-4 text-xs font-bold uppercase tracking-[0.3em] text-white transition hover:bg-red-500"
          >
            Launch Command Center
          </button>
        </motion.div>
      </motion.div>
    </motion.div>
  );
}

function StrategyRecommendationBlock({ strategy }: { strategy: StrategyData }) {
  if (strategy.fallback) {
    return (
      <div className="rounded-[1.5rem] border border-amber-500/30 bg-amber-500/10 p-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-amber-300">
          Strategy unavailable
        </p>
        <p className="mt-3 text-sm text-slate-100">
          {strategy.fallback_reason ?? "No strategy recommendation is available for this context."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-[1.5rem] border border-red-500/20 bg-red-500/[0.06] p-4">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-red-300">
          Strategy recommendation
        </p>
        <p className="mt-3 text-sm leading-7 text-slate-100">
          Baseline recommendation derived from telemetry-backed heuristics. Confidence and assumptions remain visible.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard title="Pit window" value={formatPitWindow(strategy)} />
        <MetricCard title="Undercut risk" value={capitalize(strategy.undercut_risk)} />
        <MetricCard title="Overcut risk" value={capitalize(strategy.overcut_risk)} />
        <MetricCard title="Confidence" value={capitalize(strategy.confidence_band)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ExplainabilityList title="Assumptions" items={strategy.assumptions} />
        <ExplainabilityList title="Rationale" items={strategy.rationale} />
      </div>
    </div>
  );
}

function ExplainabilityList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-500">
        {title}
      </p>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-200">
        {items.length > 0 ? (
          items.map((item) => (
            <li key={item} className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 rounded-full bg-red-400" />
              <span>{item}</span>
            </li>
          ))
        ) : (
          <li className="text-slate-500">No additional detail available.</li>
        )}
      </ul>
    </div>
  );
}

function formatPitWindow(strategy: StrategyData) {
  const window = strategy.recommended_pit_window_laps;
  if (!window || window.length < 2) {
    return "N/A";
  }
  return `Lap ${window[0]}-${window[1]}`;
}

function capitalize(value?: string) {
  if (!value) {
    return "N/A";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatChannel(
  channel?: { avg: number; unit: string },
  fractionDigits = 1,
) {
  if (!channel) {
    return "N/A";
  }

  return `${channel.avg.toFixed(fractionDigits)} ${channel.unit}`;
}

function Field({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={`space-y-2 ${className ?? ""}`.trim()}>
      <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-500">
        {label}
      </span>
      {children}
    </label>
  );
}

function ContextCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-lg font-bold text-white">{value}</p>
      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">{detail}</p>
    </div>
  );
}

function MetricCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-500">
        {title}
      </p>
      <p className="mt-3 text-lg font-bold text-white">{value}</p>
    </div>
  );
}

function PanelCard({
  eyebrow,
  title,
  body,
  children,
}: {
  eyebrow: string;
  title: string;
  body: string;
  children?: ReactNode;
}) {
  return (
    <article className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
      <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-red-300">
        {eyebrow}
      </p>
      <h3 className="mt-3 text-xl font-bold tracking-[-0.03em] text-white">{title}</h3>
      <p className="mt-3 text-sm leading-7 text-slate-400">{body}</p>
      {children}
    </article>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-white">{value}</dd>
    </div>
  );
}

function MiniSignalCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-sm text-slate-100">{value}</p>
    </div>
  );
}

function ChecklistItem({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-2 h-1.5 w-1.5 rounded-full bg-red-400" />
      <span>{text}</span>
    </li>
  );
}

function LoadingBar({ width }: { width: string }) {
  return <div className="h-3 rounded-full bg-white/8" style={{ width }} />;
}
