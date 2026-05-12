"use client";

import type { AnalyzeResponse, EventInfo, LapInfo, SavedQueryItem } from "@/services/api";
import { SESSIONS, YEARS, type SessionId } from "./constants";
import { Select, VDivider } from "./primitives";
import { formatLapTime } from "./TelemetryChart";
import { StarButton } from "./StarButton";

export function SelectorBar({
  year, setYear,
  eventName, setEvent, events, eventsLoading,
  session, setSession,
  driver, setDriver, drivers, driversLoading, driversFallback,
  setFetchedDrivers, setDriversFallback, setDriversLoading,
  lap, setLap, laps, lapsLoading, fastestLapNumber, lapOverlayLoading,
  setLaps, setFastestLapNumber, setLapsLoading, setLapOverlayLoading,
  compareDriver, setCompareDriver, compareLoading,
  setCompareSpeedSeries, setCompareLoading,
  result, isLoading, canRun, onAnalyze,
  savedQueries, onSavedQueriesChange,
}: {
  year: number;
  setYear: (n: number) => void;
  eventName: string;
  setEvent: (s: string) => void;
  events: EventInfo[];
  eventsLoading: boolean;
  session: SessionId;
  setSession: (s: SessionId) => void;
  driver: string;
  setDriver: (s: string) => void;
  drivers: readonly string[];
  driversLoading: boolean;
  driversFallback: boolean;
  setFetchedDrivers: (v: readonly string[] | null) => void;
  setDriversFallback: (v: boolean) => void;
  setDriversLoading: (v: boolean) => void;
  lap: string;
  setLap: (s: string) => void;
  laps: LapInfo[];
  lapsLoading: boolean;
  fastestLapNumber: number | null;
  lapOverlayLoading: boolean;
  setLaps: (v: LapInfo[]) => void;
  setFastestLapNumber: (n: number | null) => void;
  setLapsLoading: (v: boolean) => void;
  setLapOverlayLoading: (v: boolean) => void;
  compareDriver: string;
  setCompareDriver: (s: string) => void;
  compareLoading: boolean;
  setCompareSpeedSeries: (v: number[] | null) => void;
  setCompareLoading: (v: boolean) => void;
  result: AnalyzeResponse | null;
  isLoading: boolean;
  canRun: boolean;
  onAnalyze: () => void;
  savedQueries: SavedQueryItem[];
  onSavedQueriesChange: (items: SavedQueryItem[]) => void;
}) {
  const eventOptions   = events.map((e) => ({ id: e.name, label: e.name }));
  const sessionOptions = SESSIONS.map((s) => ({ id: s.id, label: s.label }));
  const driverOptions  = drivers.map((d) => ({ id: d, label: d }));
  const compareDriverOptions = drivers
    .filter((d) => d !== driver)
    .map((d) => ({ id: d, label: d }));
  const lapOptions = laps.map((l) => {
    const lapTime = l.lap_time_seconds != null ? formatLapTime(l.lap_time_seconds) : null;
    const tag =
      l.lap_number === fastestLapNumber ? "★ FAST"
      : l.is_pit_in ? "PIT IN"
      : l.is_pit_out ? "OUT"
      : l.compound ?? "";
    const parts = [`L${l.lap_number}`, lapTime, tag].filter(Boolean);
    return { id: String(l.lap_number), label: parts.join(" · ") };
  });

  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-border bg-surface-elevated px-5 py-2.5">
      <Select<string>
        value={String(year)}
        onChange={(v) => {
          setYear(Number(v));
          setDriver("");
          setFetchedDrivers(null);
          setDriversFallback(false);
          setLap("");
          setLaps([]);
          setFastestLapNumber(null);
          setCompareDriver("");
          setCompareSpeedSeries(null);
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
          setLap("");
          setLaps([]);
          setFastestLapNumber(null);
          setCompareDriver("");
          setCompareSpeedSeries(null);
        }}
        options={eventOptions}
        loading={eventsLoading}
        placeholder="Grand Prix"
      />
      <VDivider />

      <Select<SessionId>
        value={session}
        onChange={(v) => {
          setSession(v);
          setLap("");
          setLaps([]);
          setFastestLapNumber(null);
          setCompareSpeedSeries(null);
          if (eventName && driver) setLapsLoading(true);
          if (compareDriver) setCompareLoading(true);
        }}
        options={sessionOptions}
        placeholder="Session"
      />
      <VDivider />

      <Select<string>
        value={driver}
        onChange={(v) => {
          setDriver(v);
          setLap("");
          setLaps([]);
          setFastestLapNumber(null);
          if (eventName && v) setLapsLoading(true);
          if (v && v === compareDriver) {
            setCompareDriver("");
            setCompareSpeedSeries(null);
          }
        }}
        options={driverOptions}
        loading={driversLoading}
        placeholder="Driver"
      />
      {driversFallback && eventName ? (
        <span className="label text-foreground-faint" title="Live roster unavailable; using fallback list.">
          est.
        </span>
      ) : null}

      <VDivider />

      <Select<string>
        value={lap}
        onChange={(v) => {
          setLap(v);
          if (v && result) setLapOverlayLoading(true);
        }}
        options={lapOptions}
        loading={lapsLoading}
        placeholder="Fastest"
      />
      {lapOverlayLoading ? (
        <span className="label text-foreground-faint">syncing…</span>
      ) : null}

      <VDivider />

      <Select<string>
        value={compareDriver}
        onChange={(v) => {
          setCompareDriver(v);
          if (v) setCompareLoading(true);
          else setCompareSpeedSeries(null);
        }}
        options={compareDriverOptions}
        loading={compareLoading}
        placeholder="vs Driver"
      />

      <div className="flex-1" />

      <StarButton
        kind="analyze"
        payload={{
          query: `Analyse ${driver} ${session} session at ${eventName} ${year}`,
          driver,
          session_info: { event: eventName, year, session_type: session },
        }}
        canSave={canRun}
        savedQueries={savedQueries}
        onChange={onSavedQueriesChange}
      />

      <button
        onClick={onAnalyze}
        disabled={!canRun}
        className="btn btn--accent shrink-0 disabled:cursor-not-allowed disabled:opacity-30"
      >
        {isLoading ? "Computing…" : "Analyze"}
      </button>
    </div>
  );
}
