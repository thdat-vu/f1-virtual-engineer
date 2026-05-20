export interface AnalyzeRequest {
  query: string;
  driver?: string | null;
  session_info?: Record<string, unknown> | null;
  // Slice 1B of #168: optional 3-letter competitor code. Backend uses
  // it to measure the strategy gap against this driver instead of the
  // car directly ahead.
  target_driver?: string | null;
}

export interface TelemetryChannel {
  min: number;
  max: number;
  avg: number;
  unit: string;
  series?: number[];
}

export interface StrategyData {
  recommended_pit_window_laps: [number, number] | number[];
  target_lap: number | null;
  undercut_risk: string;
  overcut_risk: string;
  confidence_band: string;
  assumptions: string[];
  rationale: string[];
  fallback: boolean;
  fallback_reason?: string | null;
  // Slice 1A of #168: gap context surfaced from FastF1 by strategy_analyzer.
  // current_gap_seconds is populated whether the value came live, from the
  // 1.2s legacy fallback, or from an explicit caller override; gap_source
  // tells the UI which one so we can render confidence honestly.
  current_gap_seconds?: number | null;
  gap_source?: "fastf1" | "fallback" | "explicit" | null;
  competitor_ahead?: string | null;
  competitor_position_relative?: "ahead" | "behind" | null;
  gap_sampled_at_lap?: number | null;
}

export interface AnalyzeResponse {
  status: "success" | "error";
  agent_response: string;
  query: string;
  intent?: {
    intent?: string | null;
    intent_type?: "telemetry" | "strategy" | null;
    driver?: string | null;
    year?: number | null;
    event?: string | null;
    session_type?: string | null;
    needs_clarification?: boolean;
  };
  telemetry_data?: {
    sample_points?: number;
    speed?: TelemetryChannel;
    gear?: TelemetryChannel;
    rpm?: TelemetryChannel;
    throttle?: TelemetryChannel;
    brake?: TelemetryChannel;
    fallback?: boolean;
    fallback_reason?: string | null;
    lap_number?: number | null;
    lap_duration_s?: number | null;
    sector_boundaries_s?: number[];
  };
  strategy_data?: StrategyData | null;
  rationale_source?: "llm" | "template";
  rationale_job_id?: string | null;
  // ID of the persisted analyze_history row when the caller is signed
  // in. Frontends use this to track which row to poll for the async
  // rationale upgrade (#139 PR3).
  analyze_history_id?: string | null;
  execution?: AnalyzeExecution | null;
  citations?: KnowledgeCitation[];
  error?: string | null;
}

export interface KnowledgeCitation {
  id: string;
  title: string;
  source: string;
  section: string;
  topics: string[];
  snippet: string;
  score: number;
}

export interface TraceEntry {
  tool: string;
  duration_ms: number;
  status: "ok" | "error";
}

export interface AnalyzeExecution {
  step_limit: number;
  duration_limit_seconds: number;
  duration_ms: number;
  termination_reason: string;
  trace: TraceEntry[];
}

export interface EventInfo {
  name: string;
  location: string;
  round: number;
  official_name: string;
}

export interface ScheduleResponse {
  year: number;
  events: EventInfo[];
  status: "success" | "error";
  error?: string | null;
}

export interface RosterResponse {
  year: number;
  event: string;
  drivers: string[];
  source_session?: string | null;
  status: "success" | "error";
  fallback: boolean;
  fallback_reason?: string | null;
  error?: string | null;
}

export interface LapInfo {
  lap_number: number;
  lap_time_seconds: number | null;
  compound: string | null;
  is_pit_in: boolean;
  is_pit_out: boolean;
}

export interface LapListResponse {
  year: number;
  event: string;
  session_type: string;
  driver: string;
  laps: LapInfo[];
  fastest_lap_number: number | null;
  status: "success" | "error";
  fallback: boolean;
  fallback_reason?: string | null;
  error?: string | null;
}

export interface TelemetryQueryRequest {
  year: number;
  event: string;
  session_type: string;
  driver: string;
  lap_number?: number | null;
}

export interface TelemetryEnvelope {
  status: "success" | "error";
  data?: {
    driver: string;
    year: number;
    event: string;
    session_type: string;
    sample_points: number;
    speed: TelemetryChannel;
    gear: TelemetryChannel;
    rpm: TelemetryChannel;
    throttle?: TelemetryChannel | null;
    brake?: TelemetryChannel | null;
    fallback: boolean;
    fallback_reason?: string | null;
    lap_number?: number | null;
    lap_duration_s?: number | null;
    sector_boundaries_s?: number[];
  } | null;
  error?: { code: string; message: string } | null;
}

export class RateLimitError extends Error {
  readonly status = 429 as const;
  readonly retryAfterSeconds: number;
  constructor(retryAfterSeconds: number, message?: string) {
    super(message ?? `Rate limited — retry in ${retryAfterSeconds}s`);
    this.name = "RateLimitError";
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

async function readRateLimit(response: Response): Promise<RateLimitError> {
  let retryAfter = Number(response.headers.get("Retry-After")) || 10;
  let message: string | undefined;
  try {
    const body = (await response.clone().json()) as {
      error?: { retry_after_seconds?: number; message?: string };
    };
    if (body?.error?.retry_after_seconds) retryAfter = body.error.retry_after_seconds;
    if (body?.error?.message) message = body.error.message;
  } catch {
    /* non-JSON 429; keep header-based fallback */
  }
  return new RateLimitError(retryAfter, message);
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "/api";

// ─── fetchWithRetry (#160) ────────────────────────────────────────────────
// Idempotent reads occasionally fail on a wifi blip or a brief 5xx storm;
// without retry the user sees the panel stay empty until they manually
// reload. We retry network errors + 502/503/504 only — 4xx (including 429)
// surfaces to the caller so it can show the right UI, and 500/501/505+
// are likely deterministic so retrying them just delays the failure.
//
// AbortController gives each attempt its own timeout. When the timeout
// fires it produces an AbortError; we treat that as transient and retry,
// because no caller currently passes its own signal. Revisit if/when a
// caller wants user-cancellable requests — at that point we'll need to
// distinguish "we aborted you" from "you aborted us".

const RETRYABLE_STATUSES = new Set([502, 503, 504]);

interface FetchWithRetryOptions {
  /** Total attempts = retries + 1. Default 2 retries (3 attempts). */
  retries?: number;
  /** Per-attempt timeout. Defaults to 10s. */
  timeoutMs?: number;
  /** Backoff schedule. Defaults to 200ms, 800ms. */
  retryDelayMs?: (attempt: number) => number;
}

const DEFAULT_RETRY_DELAY = (attempt: number) => (attempt === 0 ? 200 : 800);

async function fetchWithRetry(
  input: RequestInfo | URL,
  init: RequestInit = {},
  opts: FetchWithRetryOptions = {},
): Promise<Response> {
  const retries = opts.retries ?? 2;
  const timeoutMs = opts.timeoutMs ?? 10_000;
  const delayFor = opts.retryDelayMs ?? DEFAULT_RETRY_DELAY;

  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(input, { ...init, signal: controller.signal });
      clearTimeout(timer);
      if (response.ok || !RETRYABLE_STATUSES.has(response.status)) {
        return response;
      }
      if (attempt < retries) {
        await delay(delayFor(attempt));
        continue;
      }
      return response;
    } catch (err) {
      clearTimeout(timer);
      lastError = err;
      const isTransient =
        err instanceof TypeError ||
        (err as { name?: string } | undefined)?.name === "AbortError";
      if (isTransient && attempt < retries) {
        await delay(delayFor(attempt));
        continue;
      }
      throw err;
    }
  }
  throw lastError ?? new Error("fetchWithRetry exhausted without response");
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Per-call timeout budgets. Schedule / driver / lap rosters call FastF1
// which can be slow on a cold cache; histories and metrics hit fast
// PostgREST + in-memory snapshots so they should bail quickly.
const TIMEOUT_LONG_MS = 10_000;
const TIMEOUT_SHORT_MS = 5_000;

export async function getEventsByYear(year: number): Promise<ScheduleResponse> {
  const response = await fetchWithRetry(`${apiBaseUrl}/events/${year}`, {}, { timeoutMs: TIMEOUT_LONG_MS });
  if (!response.ok) {
    throw new Error(`Failed to fetch events for ${year}`);
  }
  return (await response.json()) as ScheduleResponse;
}

export async function getEventDrivers(year: number, event: string): Promise<RosterResponse> {
  const response = await fetchWithRetry(
    `${apiBaseUrl}/events/${year}/${encodeURIComponent(event)}/drivers`,
    {},
    { timeoutMs: TIMEOUT_LONG_MS },
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch drivers for ${event} ${year}`);
  }
  return (await response.json()) as RosterResponse;
}

export async function getEventLaps(
  year: number,
  event: string,
  session_type: string,
  driver: string,
): Promise<LapListResponse> {
  const url = `${apiBaseUrl}/laps/${year}/${encodeURIComponent(event)}/${encodeURIComponent(session_type)}/${encodeURIComponent(driver)}`;
  const response = await fetchWithRetry(url, {}, { timeoutMs: TIMEOUT_LONG_MS });
  if (response.status === 429) throw await readRateLimit(response);
  if (!response.ok) {
    throw new Error(`Failed to fetch laps for ${driver} at ${event} ${year}`);
  }
  return (await response.json()) as LapListResponse;
}

export async function getTelemetry(
  payload: TelemetryQueryRequest,
  accessToken?: string,
): Promise<TelemetryEnvelope> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const response = await fetch(`${apiBaseUrl}/telemetry`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (response.status === 429) throw await readRateLimit(response);
  if (!response.ok) {
    throw new Error(`Telemetry request failed with status ${response.status}`);
  }
  return (await response.json()) as TelemetryEnvelope;
}

// POST /analyze is idempotent on the server side via the Idempotency-Key
// header (#161): a fresh UUID per click, the same key on every retry. If
// the first attempt's TCP connection dies after the server already picked
// up the work, the retry hits the in-flight entry — server returns 409
// Retry-After: 2 (still running) or the cached payload (already done).
// We retry exactly once, only on TypeError (network blip / DNS / abort),
// never on a 4xx/5xx — those are deterministic and would just delay the
// failure.
const ANALYZE_TIMEOUT_MS = 90_000;
const ANALYZE_RETRY_DELAY_MS = 400;

export interface AnalyzeOptions {
  // Fired right before the retry attempt sleeps. Lets the UI surface a
  // "Retrying 2/2 in 400ms…" pill (#162) without leaking retry mechanics
  // into the caller's main code path.
  onRetry?: (attempt: number, delayMs: number) => void;
}

export async function analyzeTelemetry(
  payload: AnalyzeRequest,
  accessToken?: string,
  opts: AnalyzeOptions = {},
): Promise<AnalyzeResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Idempotency-Key": crypto.randomUUID(),
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const body = JSON.stringify(payload);

  const attempt = async (): Promise<Response> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS);
    try {
      return await fetch(`${apiBaseUrl}/analyze`, {
        method: "POST",
        headers,
        body,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
  };

  let response: Response;
  try {
    response = await attempt();
  } catch (err) {
    const isTransient =
      err instanceof TypeError ||
      (err as { name?: string } | undefined)?.name === "AbortError";
    if (!isTransient) throw err;
    opts.onRetry?.(1, ANALYZE_RETRY_DELAY_MS);
    await delay(ANALYZE_RETRY_DELAY_MS);
    response = await attempt();
  }

  if (response.status === 429) throw await readRateLimit(response);
  if (!response.ok) {
    throw new Error(`Analyze request failed with status ${response.status}`);
  }

  return (await response.json()) as AnalyzeResponse;
}

export interface AnalyzeHistoryItem {
  id: string;
  query: string;
  driver: string | null;
  event: string | null;
  year: number | null;
  session_type: string | null;
  intent_type: string | null;
  rationale_source: string;
  // Populated by the async-rationale worker (#139 PR3) when the row
  // has been upgraded from `template` to `llm`. Always absent on rows
  // produced by the synchronous LLM path.
  rationale_text?: string | null;
  created_at: string;
}

export interface AnalyzeHistoryResponse {
  items: AnalyzeHistoryItem[];
}

export async function getAnalyzeHistory(
  accessToken: string,
  limit = 20,
): Promise<AnalyzeHistoryResponse> {
  const response = await fetchWithRetry(
    `${apiBaseUrl}/analyze/history?limit=${limit}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
    { timeoutMs: TIMEOUT_SHORT_MS },
  );
  if (!response.ok) {
    throw new Error(`Analyze history request failed with status ${response.status}`);
  }
  return (await response.json()) as AnalyzeHistoryResponse;
}

export interface TelemetryHistoryItem {
  id: string;
  year: number;
  event: string;
  session_type: string;
  driver: string;
  lap_number: number | null;
  created_at: string;
}

export interface TelemetryHistoryResponse {
  items: TelemetryHistoryItem[];
}

export async function getTelemetryHistory(
  accessToken: string,
  limit = 20,
): Promise<TelemetryHistoryResponse> {
  const response = await fetchWithRetry(
    `${apiBaseUrl}/telemetry/history?limit=${limit}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
    { timeoutMs: TIMEOUT_SHORT_MS },
  );
  if (!response.ok) {
    throw new Error(`Telemetry history request failed with status ${response.status}`);
  }
  return (await response.json()) as TelemetryHistoryResponse;
}

export interface RadioHistoryItem {
  id: string;
  transcript: string;
  driver: string | null;
  classification: string;
  severity: string;
  trigger_phrase: string | null;
  fallback: boolean;
  created_at: string;
}

export interface RadioHistoryResponse {
  items: RadioHistoryItem[];
}

export async function getRadioHistory(
  accessToken: string,
  limit = 20,
  driver?: string,
): Promise<RadioHistoryResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (driver) params.set("driver", driver);
  const response = await fetchWithRetry(
    `${apiBaseUrl}/radio/history?${params}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
    { timeoutMs: TIMEOUT_SHORT_MS },
  );
  if (!response.ok) {
    throw new Error(`Radio history request failed with status ${response.status}`);
  }
  return (await response.json()) as RadioHistoryResponse;
}

export type SavedQueryKind = "analyze" | "telemetry";

export interface SavedQueryItem {
  id: string;
  kind: SavedQueryKind;
  payload: Record<string, unknown>;
  label: string | null;
  created_at: string;
}

export interface SavedQueryListResponse {
  items: SavedQueryItem[];
}

export async function getSavedQueries(
  accessToken: string,
  limit = 50,
): Promise<SavedQueryListResponse> {
  const response = await fetchWithRetry(
    `${apiBaseUrl}/saved-queries?limit=${limit}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
    { timeoutMs: TIMEOUT_SHORT_MS },
  );
  if (!response.ok) {
    throw new Error(`Saved queries request failed with status ${response.status}`);
  }
  return (await response.json()) as SavedQueryListResponse;
}

export async function createSavedQuery(
  accessToken: string,
  body: { kind: SavedQueryKind; payload: Record<string, unknown>; label?: string | null },
): Promise<SavedQueryItem> {
  const response = await fetch(`${apiBaseUrl}/saved-queries`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Save query request failed with status ${response.status}`);
  }
  return (await response.json()) as SavedQueryItem;
}

export async function deleteSavedQuery(
  accessToken: string,
  id: string,
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/saved-queries/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Delete saved query failed with status ${response.status}`);
  }
}

export interface MetricsRouteSummary {
  count: number;
  p50_ms: number;
  p95_ms: number;
  max_ms: number;
  last_ms: number;
  error_rate: number;
}

export interface MetricsResponse {
  routes: Record<string, MetricsRouteSummary>;
  cache: { redis_enabled: boolean };
  workers?: {
    completed_24h: number;
    failed_24h: number;
    redis_enabled: boolean;
    queue_depth: number;
    in_flight: number;
    dlq_size: number;
    broker_reachable: boolean;
  };
}

export async function getMetrics(): Promise<MetricsResponse> {
  const response = await fetchWithRetry(
    `${apiBaseUrl}/metrics`,
    { cache: "no-store" },
    { timeoutMs: TIMEOUT_SHORT_MS },
  );
  if (!response.ok) {
    throw new Error(`Metrics request failed with status ${response.status}`);
  }
  return (await response.json()) as MetricsResponse;
}

// ─── Tyre Intelligence (#167) ─────────────────────────────────────────
// Standalone tyre snapshot — answers "how is this stint actually
// decaying right now" without needing a full strategy recommendation.
// Same fail-closed contract as /telemetry: status === "error" + a
// populated fallback envelope when FastF1 hiccups.

export interface TyreAnalyzeRequest {
  year: number;
  event: string;
  session_type: string;
  driver: string;
}

export interface TyreAnalyzeResponse {
  status: "success" | "error";
  driver: string;
  year: number;
  event: string;
  session_type: string;
  compound: string | null;
  stint_laps: number;
  decay_seconds_per_lap: number;
  cliff_lap_estimate: number | null;
  confidence_band: "high" | "medium" | "low";
  fallback: boolean;
  fallback_reason?: string | null;
}

export async function analyzeTyre(
  payload: TyreAnalyzeRequest,
): Promise<TyreAnalyzeResponse> {
  const response = await fetch(`${apiBaseUrl}/tyre/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.status === 429) throw await readRateLimit(response);
  if (!response.ok) {
    throw new Error(`Tyre analyze request failed with status ${response.status}`);
  }
  return (await response.json()) as TyreAnalyzeResponse;
}
