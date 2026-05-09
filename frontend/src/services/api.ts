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
  };
  strategy_data?: StrategyData | null;
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

export async function analyzeTelemetry(
  payload: AnalyzeRequest,
): Promise<AnalyzeResponse> {
  const response = await fetch(`${apiBaseUrl}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Analyze request failed with status ${response.status}`);
  }

  return (await response.json()) as AnalyzeResponse;
}
