export interface AnalyzeRequest {
  query: string;
  driver?: string | null;
  session_info?: Record<string, unknown> | null;
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
  error?: string | null;
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

export async function getEventsByYear(year: number): Promise<ScheduleResponse> {
  const response = await fetch(`${apiBaseUrl}/events/${year}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch events for ${year}`);
  }
  return (await response.json()) as ScheduleResponse;
}

export async function getEventDrivers(year: number, event: string): Promise<RosterResponse> {
  const response = await fetch(`${apiBaseUrl}/events/${year}/${encodeURIComponent(event)}/drivers`);
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
  const response = await fetch(url);
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

export async function analyzeTelemetry(
  payload: AnalyzeRequest,
  accessToken?: string,
): Promise<AnalyzeResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const response = await fetch(`${apiBaseUrl}/analyze`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

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
  created_at: string;
}

export interface AnalyzeHistoryResponse {
  items: AnalyzeHistoryItem[];
}

export async function getAnalyzeHistory(
  accessToken: string,
  limit = 20,
): Promise<AnalyzeHistoryResponse> {
  const response = await fetch(`${apiBaseUrl}/analyze/history?limit=${limit}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
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
  const response = await fetch(`${apiBaseUrl}/telemetry/history?limit=${limit}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
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
  const response = await fetch(`${apiBaseUrl}/radio/history?${params}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    throw new Error(`Radio history request failed with status ${response.status}`);
  }
  return (await response.json()) as RadioHistoryResponse;
}
