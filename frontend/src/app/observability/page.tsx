"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  RefreshCw,
  Server,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { getMetrics, type MetricsResponse, type MetricsRouteSummary } from "@/services/api";

const REFRESH_MS = 5_000;
const ERROR_RATE_WARN = 0.05;
const FRESH_MS = 30_000;

const fmtMs = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(2)}s` : `${n.toFixed(1)}ms`);
const fmtErrorRate = (n: number) => `${(n * 100).toFixed(1)}%`;

function freshnessStatus(updatedAt: number | null): "ok" | "warn" | "info" {
  if (updatedAt === null) return "info";
  return Date.now() - updatedAt < FRESH_MS ? "ok" : "warn";
}

export default function ObservabilityPage() {
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      try {
        const res = await getMetrics();
        if (cancelled) return;
        setData(res);
        setError(null);
        setUpdatedAt(Date.now());
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [tick]);

  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  const rows = useMemo(
    () => (data ? Object.entries(data.routes).sort(([a], [b]) => a.localeCompare(b)) : []),
    [data],
  );

  return (
    <main className="min-h-screen overflow-x-hidden bg-background text-foreground">
      <div className="hero-glow pointer-events-none fixed inset-0 opacity-40" />

      <header className="sticky top-0 z-40 border-b border-border bg-overlay backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="readout text-[length:var(--text-readout)] uppercase tracking-[var(--track-widest)] text-foreground-dim transition-colors hover:text-foreground">
            ← Back to home
          </Link>
          <LivePill />
        </div>
      </header>

      <section className="relative z-10 mx-auto max-w-6xl px-6 pt-12 pb-6">
        <div className="flex items-end justify-between gap-6 flex-wrap">
          <div>
            <p className="label mb-2 flex items-center gap-2">
              <Server size={12} /> Public · Observability
            </p>
            <h1 className="display text-[length:var(--text-h1)] text-foreground">
              Request volume &amp; latency
            </h1>
            <p className="mt-2 text-[length:var(--text-small)] text-foreground-dim">
              Rolling-window stats from <code className="font-mono">TimingMiddleware</code>. Read-only —
              counters reset on backend restart unless <code className="font-mono">REDIS_URL</code> is set.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setTick((n) => n + 1)}
            disabled={loading}
            className="flex items-center gap-2 rounded-sm border border-border-strong px-3 py-1.5 text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-dim transition-colors hover:text-foreground hover:border-foreground disabled:opacity-40"
          >
            <motion.span animate={loading ? { rotate: 360 } : { rotate: 0 }}
              transition={loading ? { repeat: Infinity, duration: 0.9, ease: "linear" } : { duration: 0.2 }}>
              <RefreshCw size={12} />
            </motion.span>
            Refresh
          </button>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3 text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-dim">
          <span className="status-pill" data-status={data?.cache.redis_enabled ? "ok" : "warn"}>
            <Database size={12} /> Redis · {data?.cache.redis_enabled ? "enabled" : "disabled"}
          </span>
          <span className="status-pill" data-status={rows.length > 0 ? "info" : undefined}>
            <TrendingUp size={12} /> Routes · {rows.length}
          </span>
          <span className="status-pill">
            <Activity size={12} /> Auto-refresh · {(REFRESH_MS / 1000).toFixed(0)}s
          </span>
          {updatedAt && (
            <span className="status-pill" data-status={freshnessStatus(updatedAt)}>
              updated {new Date(updatedAt).toLocaleTimeString()}
            </span>
          )}
        </div>
      </section>

      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-20">
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-sm border bg-surface-elevated px-4 py-3 text-[length:var(--text-small)] text-foreground status-bar"
               data-status="error"
               style={{ borderColor: "var(--status-error)", background: "var(--status-error-dim)" }}>
            <AlertTriangle size={14} style={{ color: "var(--status-error)" }} /> Failed to load metrics: {error}
          </div>
        )}

        {data?.workers && <WorkersBlock workers={data.workers} />}

        <div className="rounded-sm border border-border bg-surface-elevated overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="readout border-b border-border text-[length:var(--text-label)] uppercase tracking-[var(--track-wide)] text-foreground-dim">
                <Th>Route</Th>
                <Th align="right">Calls</Th>
                <Th align="right">p50</Th>
                <Th align="right">p95</Th>
                <Th align="right">Max</Th>
                <Th align="right">Last</Th>
                <Th align="right">Err</Th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence initial={false}>
                {rows.length === 0 && !loading && (
                  <motion.tr key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <td colSpan={7} className="px-4 py-10 text-center text-[length:var(--text-small)] text-foreground-dim">
                      No samples yet. Hit the API and refresh.
                    </td>
                  </motion.tr>
                )}
                {rows.map(([route, m], i) => (
                  <Row key={route} index={i} route={route} m={m} />
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function Row({ route, m, index }: { route: string; m: MetricsRouteSummary; index: number }) {
  const errored = m.error_rate >= ERROR_RATE_WARN;
  return (
    <motion.tr
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ delay: Math.min(index * 0.02, 0.2), duration: 0.2 }}
      className="border-b border-border last:border-0 transition-colors hover:bg-[var(--accent-dim)]"
      style={errored ? { background: "var(--status-error-dim)" } : undefined}
    >
      <td className="px-4 py-3 font-mono text-[length:var(--text-small)] text-foreground">{route}</td>
      <Td>{m.count.toLocaleString()}</Td>
      <Td>{fmtMs(m.p50_ms)}</Td>
      <Td>{fmtMs(m.p95_ms)}</Td>
      <Td>{fmtMs(m.max_ms)}</Td>
      <Td>{fmtMs(m.last_ms)}</Td>
      <td className="px-4 py-3 text-right font-mono text-[length:var(--text-small)]"
          style={{ color: errored ? "var(--status-error)" : "var(--status-ok)" }}>
        <span className="inline-flex items-center gap-1">
          {errored && <AlertTriangle size={12} />}
          {fmtErrorRate(m.error_rate)}
        </span>
      </td>
    </motion.tr>
  );
}

function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" }) {
  return <th className={`px-4 py-2 ${align === "right" ? "text-right" : ""}`}>{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 text-right font-mono text-[length:var(--text-small)] text-foreground">{children}</td>;
}

function WorkersBlock({
  workers,
}: {
  workers: NonNullable<MetricsResponse["workers"]>;
}) {
  const failed = workers.failed_24h;
  const completed = workers.completed_24h;
  const failedStatus: "ok" | "warn" = failed > 0 ? "warn" : "ok";
  const redisStatus: "ok" | "warn" = workers.redis_enabled ? "ok" : "warn";
  const dlqStatus: "ok" | "warn" = workers.dlq_size > 0 ? "warn" : "ok";
  const brokerStatus: "ok" | "warn" = workers.broker_reachable ? "ok" : "warn";
  const queueStatus: "ok" | "warn" =
    !workers.broker_reachable || workers.queue_depth > 50 ? "warn" : "ok";

  return (
    <div className="mb-6 space-y-4">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <p className="label flex items-center gap-2">
            <Activity size={12} /> Workers · last 24h
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <WorkerCard
            icon={<CheckCircle2 size={14} />}
            label="Completed"
            value={completed.toLocaleString()}
            status="ok"
          />
          <WorkerCard
            icon={<XCircle size={14} />}
            label="Failed"
            value={failed.toLocaleString()}
            status={failedStatus}
          />
          <WorkerCard
            icon={<Database size={14} />}
            label="Redis backend"
            value={workers.redis_enabled ? "enabled" : "disabled"}
            status={redisStatus}
          />
        </div>
        {!workers.redis_enabled && (
          <p className="readout mt-2 text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-dim">
            Counters reset on backend restart — set <code className="font-mono">REDIS_URL</code> for 24h persistence.
          </p>
        )}
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <p className="label flex items-center gap-2">
            <Activity size={12} /> Workers · live (broker)
          </p>
          <span className="status-pill" data-status={brokerStatus}>
            broker · {workers.broker_reachable ? "reachable" : "unreachable"}
          </span>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <WorkerCard
            icon={<TrendingUp size={14} />}
            label="Queue depth"
            value={workers.queue_depth.toLocaleString()}
            status={queueStatus}
          />
          <WorkerCard
            icon={<Activity size={14} />}
            label="In flight"
            value={workers.in_flight.toLocaleString()}
            status="ok"
          />
          <WorkerCard
            icon={<AlertTriangle size={14} />}
            label="DLQ size"
            value={workers.dlq_size.toLocaleString()}
            status={dlqStatus}
          />
        </div>
        {!workers.broker_reachable && (
          <p className="readout mt-2 text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)] text-foreground-dim">
            RabbitMQ Management API unreachable — set <code className="font-mono">RABBITMQ_PASSWORD</code> + bring up the broker via <code className="font-mono">make stack-up</code> to populate live counters.
          </p>
        )}
      </div>
    </div>
  );
}

function WorkerCard({
  icon,
  label,
  value,
  status,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  status: "ok" | "warn";
}) {
  const color = `var(--status-${status})`;
  const bg = `var(--status-${status}-dim)`;
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-sm border bg-surface-elevated p-4"
      style={{ borderColor: color, background: bg }}
    >
      <p className="label mb-2 flex items-center gap-2" style={{ color }}>
        {icon} {label}
      </p>
      <p className="display text-[length:var(--text-h2)] text-foreground">{value}</p>
    </motion.div>
  );
}

function LivePill() {
  return (
    <span className="readout inline-flex items-center gap-2 rounded-sm border px-2.5 py-1 text-[length:var(--text-readout)] uppercase tracking-[var(--track-wide)]"
          style={{ borderColor: "var(--status-ok)", background: "var(--status-ok-dim)", color: "var(--status-ok)" }}>
      <motion.span
        className="block h-1.5 w-1.5 rounded-full"
        style={{ background: "var(--status-ok)" }}
        animate={{ opacity: [0.3, 1, 0.3], scale: [0.85, 1.1, 0.85] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      />
      Live
    </span>
  );
}
