"use client";

import { useEffect, useRef, useState } from "react";

import { getAnalyzeHistory } from "@/services/api";

const POLL_INTERVAL_MS = 3_000;
const TIMEOUT_MS = 60_000;

export type RationaleUpgradeStatus = "idle" | "pending" | "upgraded" | "timeout" | "error";

export interface UseRationaleUpgradeArgs {
  /** ID of the analyze_history row the worker is back-filling. */
  rowId: string | null | undefined;
  /** Initial source returned synchronously by /analyze. */
  initialSource: "llm" | "template" | string | null | undefined;
  /** Access token for /analyze/history. Hook is a no-op without one. */
  accessToken: string | null | undefined;
}

export interface UseRationaleUpgradeResult {
  status: RationaleUpgradeStatus;
  /** Populated once the row flips to rationale_source='llm'. */
  rationaleText: string | null;
}

interface AsyncResult {
  rowId: string;
  status: "upgraded" | "timeout" | "error";
  text: string | null;
}

/**
 * Polls /analyze/history until the row matching `rowId` flips its
 * `rationale_source` from `template` to `llm`, then exposes the
 * back-filled `rationale_text` so the caller can swap the displayed
 * response.
 *
 * Status is derived: when there's an active row to poll and no async
 * result yet, we report "pending"; once the poll loop resolves we keep
 * the result in state and surface it. This keeps the effect free of
 * synchronous setState calls — only async callbacks mutate state.
 */
export function useRationaleUpgrade({
  rowId,
  initialSource,
  accessToken,
}: UseRationaleUpgradeArgs): UseRationaleUpgradeResult {
  const [asyncResult, setAsyncResult] = useState<AsyncResult | null>(null);
  const cancelledRef = useRef(false);

  const shouldPoll = Boolean(
    rowId && accessToken && initialSource !== "llm",
  );

  useEffect(() => {
    cancelledRef.current = false;
    if (!shouldPoll || !rowId || !accessToken) {
      return;
    }

    const startedAt = Date.now();
    let intervalId: ReturnType<typeof setInterval> | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const stop = (next: AsyncResult["status"], text: string | null) => {
      if (cancelledRef.current) return;
      if (intervalId) clearInterval(intervalId);
      if (timeoutId) clearTimeout(timeoutId);
      setAsyncResult({ rowId, status: next, text });
    };

    const poll = async () => {
      if (cancelledRef.current) return;
      if (Date.now() - startedAt >= TIMEOUT_MS) {
        stop("timeout", null);
        return;
      }
      try {
        const res = await getAnalyzeHistory(accessToken, 20);
        if (cancelledRef.current) return;
        const match = res.items.find((item) => item.id === rowId);
        if (match && match.rationale_source === "llm") {
          stop("upgraded", match.rationale_text ?? null);
        }
      } catch {
        // Transient network/API errors during poll are expected — keep
        // polling until the timeout. We absorb and retry rather than
        // surfacing every blip to the UI.
      }
    };

    // Fire one immediate poll so a fast-finishing job doesn't always
    // wait the full interval before being detected.
    void poll();
    intervalId = setInterval(() => void poll(), POLL_INTERVAL_MS);
    timeoutId = setTimeout(() => stop("timeout", null), TIMEOUT_MS);

    return () => {
      cancelledRef.current = true;
      if (intervalId) clearInterval(intervalId);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [rowId, accessToken, shouldPoll]);

  const matched = asyncResult && asyncResult.rowId === rowId ? asyncResult : null;
  const status: RationaleUpgradeStatus = !shouldPoll
    ? "idle"
    : matched
      ? matched.status
      : "pending";
  const rationaleText = matched ? matched.text : null;

  return { status, rationaleText };
}
