"use client";

import { useEffect, useState, useCallback } from "react";
import { analyzeTelemetry, getEventDrivers, getEventLaps, getEventsByYear, getLapDelta, getTelemetry, RateLimitError } from "@/services/api";
import type { AnalyzeHistoryItem, AnalyzeResponse, EventInfo, LapDeltaResponse, LapInfo, SavedQueryItem, TelemetryHistoryItem } from "@/services/api";
import { useMissionStore } from "@/lib/store";
import { useSupabase } from "@/components/auth/SupabaseProvider";
import {
  FALLBACK_DRIVERS, MissionFooter, MissionHeader, NavRail,
  SelectorBar, StrategyHUD, TelemetryChartGrid, type SessionId,
} from "@/components/mission-control";
import { defaultSeason } from "@/lib/f1-seasons";

export default function MissionControlPage() {
  const { theme, setTheme, result, setResult, isLoading, setIsLoading } = useMissionStore();
  const { session: authSession } = useSupabase();
  const [historyRefreshSignal, setHistoryRefreshSignal] = useState(0);
  const [telemetryHistoryRefreshSignal, setTelemetryHistoryRefreshSignal] = useState(0);
  const [radioHistoryRefreshSignal] = useState(0);
  const [savedQueries, setSavedQueries] = useState<SavedQueryItem[]>([]);

  const [year, setYear]       = useState<number>(defaultSeason());
  const [eventName, setEvent] = useState<string>("");
  const [session, setSession] = useState<SessionId>("R");
  const [driver, setDriver]   = useState<string>("");

  const [events, setEvents]               = useState<EventInfo[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  const [fetchedDrivers, setFetchedDrivers]   = useState<readonly string[] | null>(null);
  const [driversLoading, setDriversLoading]   = useState(false);
  const [driversFallback, setDriversFallback] = useState(false);

  const drivers: readonly string[] =
    eventName && fetchedDrivers && fetchedDrivers.length > 0 ? fetchedDrivers : FALLBACK_DRIVERS;

  // lap === "" means "Fastest" (default — analyze already picks fastest).
  // A non-empty value triggers a /telemetry override patching the chart series.
  const [lap, setLap]                           = useState<string>("");
  const [laps, setLaps]                         = useState<LapInfo[]>([]);
  const [fastestLapNumber, setFastestLapNumber] = useState<number | null>(null);
  const [lapsLoading, setLapsLoading]           = useState(false);
  const [lapOverlayLoading, setLapOverlayLoading] = useState(false);

  // When set, the Speed chart overlays this driver's fastest-lap trace as a dashed muted line.
  const [compareDriver, setCompareDriver]             = useState<string>("");
  const [compareSpeedSeries, setCompareSpeedSeries]   = useState<number[] | null>(null);
  const [compareLoading, setCompareLoading]           = useState(false);

  // Issue #184: per-distance Δt(reference vs compare). Loading state is
  // derived in the chart from "compareDriver set but no payload" — no
  // separate flag needed, which also keeps us out of the
  // react-hooks/set-state-in-effect rule.
  const [lapDelta, setLapDelta] = useState<LapDeltaResponse | null>(null);

  // Issue #182: explicit intent toggle. Default "telemetry" preserves the
  // legacy fastest-lap compare behavior; "strategy" routes the analyze
  // query through the regex classifier into strategy_analyzer so the Pit
  // Window block + slice 1A→1D fields actually render.
  const [intent, setIntent] = useState<"telemetry" | "strategy">("telemetry");

  // Cleared on the next successful Analyze; surfaced in StrategyHUD when set.
  const [rateLimitMessage, setRateLimitMessage] = useState<string | null>(null);

  // Retry status for /analyze (#162). 'idle' once a request settles; 'retrying'
  // while the network-blip retry is mid-flight; 'failed' if even the retry
  // didn't surface a response — drives the "Try again" CTA in the HUD.
  const [retryState, setRetryState] = useState<"idle" | "retrying" | "failed">("idle");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    getEventsByYear(year)
      .then((res) => { if (!cancelled) { setEvents(res.events ?? []); setEvent(""); } })
      .catch(() => { if (!cancelled) setEvents([]); })
      .finally(() => { if (!cancelled) setEventsLoading(false); });
    return () => { cancelled = true; };
  }, [year]);

  // Live driver roster; falls back to static list if backend has none yet.
  useEffect(() => {
    if (!eventName) return;
    let cancelled = false;
    getEventDrivers(year, eventName)
      .then((res) => {
        if (cancelled) return;
        const ok = res.drivers.length > 0;
        setFetchedDrivers(ok ? res.drivers : null);
        setDriversFallback(ok ? res.fallback : true);
      })
      .catch(() => { if (!cancelled) { setFetchedDrivers(null); setDriversFallback(true); } })
      .finally(() => { if (!cancelled) setDriversLoading(false); });
    return () => { cancelled = true; };
  }, [year, eventName]);

  // Lap roster — empty hides the lap selector so the UI doesn't pretend a choice is available.
  useEffect(() => {
    if (!eventName || !driver) return;
    let cancelled = false;
    getEventLaps(year, eventName, session, driver)
      .then((res) => { if (!cancelled) { setLaps(res.laps ?? []); setFastestLapNumber(res.fastest_lap_number); } })
      .catch(() => { if (!cancelled) { setLaps([]); setFastestLapNumber(null); } })
      .finally(() => { if (!cancelled) setLapsLoading(false); });
    return () => { cancelled = true; };
  }, [year, eventName, session, driver]);

  // Patch only `telemetry_data` on the existing analysis when a non-fastest lap is picked.
  // Agent narrative intentionally stays untouched — that requires a fresh /analyze run.
  useEffect(() => {
    if (!result || !eventName || !driver || lap === "") return;
    const lapNumber = Number(lap);
    if (!Number.isFinite(lapNumber)) return;
    if (result.telemetry_data?.lap_number === lapNumber) return;

    let cancelled = false;
    getTelemetry(
      { year, event: eventName, session_type: session, driver, lap_number: lapNumber },
      authSession?.access_token,
    )
      .then((res) => {
        if (cancelled || !res.data) return;
        setResult({
          ...result,
          telemetry_data: {
            sample_points: res.data.sample_points,
            speed: res.data.speed,
            gear: res.data.gear,
            rpm: res.data.rpm,
            throttle: res.data.throttle ?? undefined,
            brake: res.data.brake ?? undefined,
            fallback: res.data.fallback,
            fallback_reason: res.data.fallback_reason ?? null,
            lap_number: res.data.lap_number ?? lapNumber,
            lap_duration_s: res.data.lap_duration_s ?? null,
            sector_boundaries_s: res.data.sector_boundaries_s ?? [],
          },
        });
        if (authSession && !res.data.fallback) setTelemetryHistoryRefreshSignal((n) => n + 1);
      })
      .catch(() => { /* silent — chart keeps existing series */ })
      .finally(() => { if (!cancelled) setLapOverlayLoading(false); });
    return () => { cancelled = true; };
  }, [lap, result, eventName, driver, session, year, setResult, authSession]);

  // Compare-driver fastest-lap speed trace.
  useEffect(() => {
    if (!compareDriver || !eventName) return;
    let cancelled = false;
    getTelemetry(
      { year, event: eventName, session_type: session, driver: compareDriver },
      authSession?.access_token,
    )
      .then((res) => {
        if (cancelled) return;
        setCompareSpeedSeries(res.data?.speed?.series ?? null);
        if (authSession && res.data && !res.data.fallback) {
          setTelemetryHistoryRefreshSignal((n) => n + 1);
        }
      })
      .catch(() => { if (!cancelled) setCompareSpeedSeries(null); })
      .finally(() => { if (!cancelled) setCompareLoading(false); });
    return () => { cancelled = true; };
  }, [compareDriver, year, eventName, session, authSession]);

  // Issue #184: lap-delta fetch. Triggers only when both drivers and a
  // session/event are pinned. We don't synchronously flip a loading
  // flag here — the chart derives "loading" as "compareDriver set but
  // payload doesn't yet match the requested pair" (see lapDeltaLoading
  // below). Keeps the effect side-effect-free at sync time and
  // satisfies react-hooks/set-state-in-effect.
  useEffect(() => {
    if (!compareDriver || !driver || !eventName || compareDriver === driver) return;
    let cancelled = false;
    getLapDelta({
      year,
      event: eventName,
      session_type: session,
      reference_driver: driver,
      compare_driver: compareDriver,
    })
      .then((res) => { if (!cancelled) setLapDelta(res); })
      .catch(() => { if (!cancelled) setLapDelta(null); });
    return () => { cancelled = true; };
  }, [driver, compareDriver, year, eventName, session]);

  const canRun = !isLoading && !!eventName && !!driver;

  // Single source of truth for the analyze call. Takes explicit args so
  // history-click handlers can replay against fresh values without
  // waiting for setState to flush. handleAnalyze and handleSelect*
  // both funnel through here.
  const runAnalyze = useCallback(async (args: {
    year: number;
    eventName: string;
    session: SessionId;
    driver: string;
    targetDriver?: string;
    intent?: "telemetry" | "strategy";
  }) => {
    setIsLoading(true);
    setRateLimitMessage(null);
    setRetryState("idle");
    try {
      // Strategy keyword in the query is what makes the backend regex
      // classifier route to strategy_analyzer (#182). Telemetry mode
      // keeps the original phrasing so existing history rows still
      // round-trip with their telemetry intent.
      const strategyMode = (args.intent ?? intent) === "strategy";
      const query = strategyMode
        ? args.targetDriver
          ? `Pit strategy for ${args.driver} chasing ${args.targetDriver} at ${args.eventName} ${args.year} ${args.session}`
          : `Pit strategy for ${args.driver} at ${args.eventName} ${args.year} ${args.session}`
        : `Analyse ${args.driver} ${args.session} session at ${args.eventName} ${args.year}`;
      const res = await analyzeTelemetry(
        {
          query,
          driver: args.driver,
          session_info: { event: args.eventName, year: args.year, session_type: args.session },
          // Slice 1B of #168: when the user picked a "vs" driver, reuse
          // it as the strategy target so the gap line in the HUD reflects
          // their actual rival rather than whoever's running ahead.
          target_driver: args.targetDriver || null,
        },
        authSession?.access_token,
        { onRetry: () => setRetryState("retrying") },
      );
      setResult(res as AnalyzeResponse);
      setRetryState("idle");
      if (authSession) setHistoryRefreshSignal((n) => n + 1);
    } catch (err) {
      if (err instanceof RateLimitError) {
        setRateLimitMessage(`Rate limited — retry in ${err.retryAfterSeconds}s`);
        setRetryState("idle");
      } else {
        setRetryState("failed");
      }
    } finally {
      setIsLoading(false);
    }
  }, [setIsLoading, setResult, authSession, intent]);

  const handleAnalyze = useCallback(async () => {
    if (!canRun) return;
    await runAnalyze({ year, eventName, session, driver, targetDriver: compareDriver, intent });
  }, [canRun, year, eventName, session, driver, compareDriver, intent, runAnalyze]);

  const handleSelectHistory = useCallback((item: AnalyzeHistoryItem) => {
    const nextYear = item.year ?? year;
    const nextEvent = item.event ?? eventName;
    const nextSession = (item.session_type as SessionId | null) ?? session;
    const nextDriver = item.driver ?? driver;
    if (item.year) setYear(item.year);
    if (item.event) setEvent(item.event);
    if (item.session_type) setSession(item.session_type as SessionId);
    if (item.driver) setDriver(item.driver);
    if (nextEvent && nextDriver) {
      void runAnalyze({ year: nextYear, eventName: nextEvent, session: nextSession, driver: nextDriver });
    }
  }, [year, eventName, session, driver, runAnalyze]);

  const handleSelectTelemetryHistory = useCallback((item: TelemetryHistoryItem) => {
    setYear(item.year);
    setEvent(item.event);
    setSession(item.session_type as SessionId);
    setDriver(item.driver);
    setLap(item.lap_number != null ? String(item.lap_number) : "");
    if (item.event && item.driver) {
      void runAnalyze({
        year: item.year,
        eventName: item.event,
        session: item.session_type as SessionId,
        driver: item.driver,
      });
    }
  }, [runAnalyze]);

  const handleSelectSaved = useCallback((item: SavedQueryItem) => {
    const p = item.payload as Record<string, unknown>;
    if (item.kind === "analyze") {
      const info = (p.session_info as Record<string, unknown> | undefined) ?? {};
      const nextYear = typeof info.year === "number" ? info.year : year;
      const nextEvent = typeof info.event === "string" ? info.event : eventName;
      const nextSession = (typeof info.session_type === "string" ? info.session_type : session) as SessionId;
      const nextDriver = typeof p.driver === "string" ? p.driver : driver;
      if (typeof info.year === "number") setYear(info.year);
      if (typeof info.event === "string") setEvent(info.event);
      if (typeof info.session_type === "string") setSession(info.session_type as SessionId);
      if (typeof p.driver === "string") setDriver(p.driver);
      // compare_driver was added in #153; older rows may lack it, treat
      // an explicit null or absence the same as "no comparison".
      if (typeof p.compare_driver === "string") setCompareDriver(p.compare_driver);
      else setCompareDriver("");
      if (nextEvent && nextDriver) {
        void runAnalyze({ year: nextYear, eventName: nextEvent, session: nextSession, driver: nextDriver });
      }
    } else if (item.kind === "telemetry") {
      const nextYear = typeof p.year === "number" ? p.year : year;
      const nextEvent = typeof p.event === "string" ? p.event : eventName;
      const nextSession = (typeof p.session_type === "string" ? p.session_type : session) as SessionId;
      const nextDriver = typeof p.driver === "string" ? p.driver : driver;
      if (typeof p.year === "number") setYear(p.year);
      if (typeof p.event === "string") setEvent(p.event);
      if (typeof p.session_type === "string") setSession(p.session_type as SessionId);
      if (typeof p.driver === "string") setDriver(p.driver);
      if (typeof p.lap_number === "number") setLap(String(p.lap_number));
      else setLap("");
      if (nextEvent && nextDriver) {
        void runAnalyze({ year: nextYear, eventName: nextEvent, session: nextSession, driver: nextDriver });
      }
    }
  }, [year, eventName, session, driver, runAnalyze]);

  const tel     = result?.telemetry_data;
  const strat   = result?.strategy_data;
  const hasData = !isLoading && !!result;
  const animKey = result ? 1 : 0;

  // Lap-delta loading is derived, not stored — the chart treats the
  // request as in-flight whenever a compare driver is picked but the
  // latest payload doesn't yet describe that driver pair.
  const lapDeltaLoading = Boolean(
    compareDriver && driver && (
      !lapDelta ||
      lapDelta.reference_driver !== driver ||
      lapDelta.compare_driver !== compareDriver
    ),
  );

  const displayDriver = result?.intent?.driver ?? driver ?? "—";
  const displayEvent  = result?.intent?.event  ?? eventName ?? "—";
  const displayLap =
    tel?.lap_number != null
      ? `LAP ${tel.lap_number}${tel.lap_number === fastestLapNumber ? " · FAST" : ""}`
      : hasData ? "FAST LAP" : null;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      <NavRail />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <MissionHeader
          displayDriver={displayDriver} displayEvent={displayEvent} displayLap={displayLap}
          theme={theme} setTheme={setTheme}
        />

        <SelectorBar
          year={year} setYear={setYear}
          eventName={eventName} setEvent={setEvent} events={events} eventsLoading={eventsLoading}
          session={session} setSession={setSession}
          driver={driver} setDriver={setDriver} drivers={drivers}
          driversLoading={driversLoading} driversFallback={driversFallback}
          setFetchedDrivers={setFetchedDrivers} setDriversFallback={setDriversFallback}
          setDriversLoading={setDriversLoading}
          lap={lap} setLap={setLap} laps={laps} lapsLoading={lapsLoading}
          fastestLapNumber={fastestLapNumber} lapOverlayLoading={lapOverlayLoading}
          setLaps={setLaps} setFastestLapNumber={setFastestLapNumber}
          setLapsLoading={setLapsLoading} setLapOverlayLoading={setLapOverlayLoading}
          compareDriver={compareDriver} setCompareDriver={setCompareDriver}
          compareLoading={compareLoading}
          setCompareSpeedSeries={setCompareSpeedSeries} setCompareLoading={setCompareLoading}
          intent={intent} setIntent={setIntent}
          result={result} isLoading={isLoading} canRun={canRun} onAnalyze={handleAnalyze}
          savedQueries={savedQueries} onSavedQueriesChange={setSavedQueries}
        />

        <TelemetryChartGrid
          tel={tel} isLoading={isLoading} hasData={hasData} animateKey={animKey}
          compareDriver={compareDriver} compareSpeedSeries={compareSpeedSeries}
          driver={driver} lapDelta={lapDelta} lapDeltaLoading={lapDeltaLoading}
        />

        <MissionFooter tel={tel} strat={strat} hasData={hasData} execution={result?.execution} />
      </div>

      <StrategyHUD
        result={result} strat={strat} isLoading={isLoading} hasData={hasData}
        session={session} theme={theme} rateLimitMessage={rateLimitMessage}
        retryState={retryState} onRetryClick={handleAnalyze}
        year={year} eventName={eventName} driver={driver}
        targetDriver={compareDriver}
        historyRefreshSignal={historyRefreshSignal}
        onSelectHistory={handleSelectHistory}
        telemetryHistoryRefreshSignal={telemetryHistoryRefreshSignal}
        onSelectTelemetryHistory={handleSelectTelemetryHistory}
        radioHistoryRefreshSignal={radioHistoryRefreshSignal}
        savedQueries={savedQueries}
        onSavedQueriesChange={setSavedQueries}
        onSelectSaved={handleSelectSaved}
      />
    </div>
  );
}
