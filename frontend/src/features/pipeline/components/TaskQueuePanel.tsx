import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ChevronRight,
  Inbox,
  Layers3,
  ListChecks,
  Radio,
  X,
} from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";
import { usePipelineRuns } from "../hooks/usePipelineRuns";
import { TaskQueueRow } from "./TaskQueueRow";
import type { PipelineRunSummary } from "../types/pipeline";

interface TaskQueuePanelProps {
  onClose?: () => void;
}

/** Cap the number of recent (terminal) runs rendered to keep the panel light. */
const RECENT_LIMIT = 8;

type TabKey = "active" | "recent" | "failed";

function isActive(run: PipelineRunSummary): boolean {
  return run.pipeline_status === "running" || run.pipeline_status === "pending";
}

function isFailed(run: PipelineRunSummary): boolean {
  return run.pipeline_status === "failed";
}

export function TaskQueuePanel({ onClose }: TaskQueuePanelProps) {
  const { data, isLoading, isError, dataUpdatedAt } = usePipelineRuns();
  const [tab, setTab] = useState<TabKey>("active");

  // Memoise the underlying array reference so downstream useMemo callbacks
  // (which depend on `runs`) do not recompute on every render when
  // `data?.items` is undefined and the `?? []` fallback allocates a fresh
  // array. Matches the pattern already used for chat messages.
  const runs = useMemo(() => data?.items ?? [], [data?.items]);
  const { activeRuns, recentRuns, failedRuns } = useMemo(() => {
    const active = runs.filter(isActive);
    const failed = runs.filter(isFailed);
    // Sort active by started_at desc (newest first); terminal runs likewise.
    const activeSorted = [...active].sort((a, b) => {
      const ta = a.started_at ? new Date(a.started_at).getTime() : 0;
      const tb = b.started_at ? new Date(b.started_at).getTime() : 0;
      return tb - ta;
    });
    const failedSorted = [...failed].sort((a, b) => {
      const ta = a.completed_at ?? a.started_at;
      const tb = b.completed_at ?? b.started_at;
      const tA = ta ? new Date(ta).getTime() : 0;
      const tB = tb ? new Date(tb).getTime() : 0;
      return tB - tA;
    });
    const terminal = runs
      .filter((r) => !isActive(r) && !isFailed(r))
      .sort((a, b) => {
        const ta = a.completed_at ?? a.started_at;
        const tb = b.completed_at ?? b.started_at;
        const tA = ta ? new Date(ta).getTime() : 0;
        const tB = tb ? new Date(tb).getTime() : 0;
        return tB - tA;
      })
      .slice(0, RECENT_LIMIT);
    return { activeRuns: activeSorted, recentRuns: terminal, failedRuns: failedSorted };
  }, [runs]);

  const total = data?.total ?? 0;
  const visible = tab === "active" ? activeRuns : tab === "failed" ? failedRuns : recentRuns;
  const emptyMessage =
    tab === "active"
      ? "No active pipelines"
      : tab === "failed"
        ? "No failed pipelines"
        : "No recent pipelines";

  const updatedAt = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })
    : null;

  return (
      <aside
        style={{
          display: "flex",
          height: "100%",
          width: 320,
          flexShrink: 0,
          flexDirection: "column",
          borderLeft: "1px solid #f3f4f6",
          backgroundColor: "#fafbfc",
          backdropFilter: "blur(4px)",
        }}
        aria-label="Task queue"
      >
        {/* Header */}
        <header style={{ display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid #f3f4f6", padding: "12px 16px" }}>
          <span
            style={{
              display: "flex",
              height: 28,
              width: 28,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 6,
              background: "linear-gradient(to bottom right, var(--color-primary-500, #06b6d4), #2563eb)",
              color: "#fff",
              boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            }}
          >
            <ListChecks style={{ width: 14, height: 14 }} aria-hidden />
          </span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h2 style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.025em", color: "#111827" }}>
              Task Queue
            </h2>
            <p style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 10.5, color: "#6b7280" }}>
              {activeRuns.length > 0 ? (
                <>
                  <span style={{ fontWeight: 500, color: "var(--color-primary-700, #0e7490)" }}>
                    {activeRuns.length}
                  </span>{" "}
                  active · {total} total
                </>
              ) : (
                <>{total} total pipelines</>
              )}
            </p>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close task queue"
              className="tqp-close-btn"
            >
              <X style={{ width: 16, height: 16 }} />
            </button>
          )}
        </header>

        {/* Tabs */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "12px 12px 0" }}>
          <TabButton
            active={tab === "active"}
            onClick={() => setTab("active")}
            icon={<Radio style={{ width: 12, height: 12 }} />}
            label="Active"
            count={activeRuns.length}
            pulse={activeRuns.length > 0}
          />
          <TabButton
            active={tab === "recent"}
            onClick={() => setTab("recent")}
            icon={<Inbox style={{ width: 12, height: 12 }} />}
            label="Recent"
            count={recentRuns.length}
          />
          <TabButton
            active={tab === "failed"}
            onClick={() => setTab("failed")}
            icon={<AlertTriangle style={{ width: 12, height: 12 }} />}
            label="Failed"
            count={failedRuns.length}
            pulse={failedRuns.length > 0 && tab !== "failed"}
          />
          <Link
            to="/pipeline"
            className="tqp-view-all"
            title="Open pipeline page"
          >
            <span>View all</span>
            <ChevronRight style={{ width: 12, height: 12 }} />
          </Link>
        </div>

        {/* Body */}
        <div style={{ minHeight: 0, flex: 1, overflowY: "auto", padding: "8px 8px 12px" }}>
          {isLoading && runs.length === 0 ? (
            <LoadingSkeleton />
          ) : isError ? (
            <ErrorState />
          ) : visible.length === 0 ? (
            <EmptyState message={emptyMessage} />
          ) : (
            <ul style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {visible.map((run) => (
                <li key={run.processing_run_id}>
                  <TaskQueueRow run={run} />
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer: last sync indicator */}
        <footer
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            borderTop: "1px solid #f3f4f6",
            padding: "8px 16px",
            fontSize: 10,
            color: "#9ca3af",
          }}
        >
          <Activity style={{ width: 12, height: 12 }} aria-hidden />
          <span style={{ fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums" }}>
            {updatedAt ? `Synced ${updatedAt}` : "Syncing…"}
          </span>
          <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4 }}>
            <Layers3 style={{ width: 12, height: 12 }} aria-hidden />
            <span>Live</span>
          </span>
        </footer>
      </aside>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  count?: number;
  pulse?: boolean;
}

function TabButton({ active, onClick, icon, label, count, pulse }: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="tqp-tab-btn"
      style={
        active
          ? { backgroundColor: "#111827", color: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }
          : { color: "#4b5563" }
      }
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = "#f3f4f6";
          e.currentTarget.style.color = "#111827";
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = "";
          e.currentTarget.style.color = "#4b5563";
        }
      }}
    >
      <span style={{ color: active ? "#fff" : "#9ca3af" }}>{icon}</span>
      <span>{label}</span>
      {typeof count === "number" && count > 0 && (
        <span
          style={{
            minWidth: 18,
            borderRadius: 9999,
            padding: "1px 4px",
            fontSize: 9.5,
            fontWeight: 600,
            fontVariantNumeric: "tabular-nums",
            backgroundColor: active ? "rgba(255,255,255,0.2)" : "#e5e7eb",
            color: active ? "#fff" : "#374151",
          }}
        >
          {count}
        </span>
      )}
      {pulse && !active && (
        <span style={{ position: "relative", marginLeft: 2, display: "flex", width: 6, height: 6 }}>
          <span
            style={{
              position: "absolute",
              display: "inline-flex",
              height: "100%",
              width: "100%",
              animation: "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite",
              borderRadius: "50%",
              backgroundColor: "#38bdf8",
              opacity: 0.75,
            }}
          />
          <span
            style={{
              position: "relative",
              display: "inline-flex",
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: "var(--color-primary-600, #0891b2)",
            }}
          />
        </span>
      )}
    </button>
  );
}

function LoadingSkeleton() {
  return (
    <ul style={{ display: "flex", flexDirection: "column", gap: 8, padding: "0 4px" }}>
      {Array.from({ length: 3 }).map((_, i) => (
        <li key={i} style={{ borderRadius: 8, border: "1px solid #f3f4f6", backgroundColor: "#fff", padding: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Skeleton variant="circle" width={10} height={10} />
            <Skeleton width={64} height={10} />
            <Skeleton variant="pill" width={40} height={12} style={{ marginLeft: "auto" }} />
          </div>
          <Skeleton width="75%" height={8} style={{ marginTop: 8 }} />
          <Skeleton width="100%" height={6} style={{ marginTop: 8 }} />
        </li>
      ))}
    </ul>
  );
}

function ErrorState() {
  return (
    <div
      style={{
        margin: "24px 12px 0",
        borderRadius: 8,
        border: "1px solid #fee2e2",
        backgroundColor: "rgba(254,242,242,0.6)",
        padding: 16,
        textAlign: "center",
      }}
    >
      <p style={{ fontSize: 11.5, fontWeight: 500, color: "#b91c1c" }}>
        Unable to load pipelines
      </p>
      <p style={{ marginTop: 4, fontSize: 10.5, lineHeight: 1.625, color: "rgba(220,38,38,0.8)" }}>
        Check the backend connection and try again.
      </p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div style={{ margin: "40px 12px 0", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center" }}>
      <span
        style={{
          display: "flex",
          height: 40,
          width: 40,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "50%",
          backgroundColor: "#f3f4f6",
          color: "#9ca3af",
        }}
      >
        <Inbox style={{ width: 16, height: 16 }} aria-hidden />
      </span>
      <p style={{ marginTop: 12, fontSize: 12, fontWeight: 500, color: "#374151" }}>{message}</p>
      <p style={{ marginTop: 4, maxWidth: 220, fontSize: 10.5, lineHeight: 1.625, color: "#6b7280" }}>
        Pipelines submitted from this chat will appear here in real time.
      </p>
    </div>
  );
}
