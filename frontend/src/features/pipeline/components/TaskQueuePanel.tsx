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
import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
  const { data, isLoading, isError, dataUpdatedAt } = usePipelineRuns();
  const [tab, setTab] = useState<TabKey>("active");
  const runs = useMemo(() => data?.items ?? [], [data?.items]);
  const { activeRuns, recentRuns, failedRuns } = useMemo(() => {
    const active = runs.filter(isActive);
    const failed = runs.filter(isFailed);
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
      ? t("pipeline.queue.emptyActive")
      : tab === "failed"
        ? t("pipeline.queue.emptyFailed")
        : t("pipeline.queue.emptyRecent");

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
        borderLeft: "1px solid var(--color-bg-muted)",
        backgroundColor: "var(--color-bg)",
        backdropFilter: "blur(4px)",
      }}
      aria-label={t("pipeline.queue.ariaLabel")}
    >
      {/* Header */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderBottom: "1px solid var(--color-bg-muted)",
          padding: "12px 16px",
        }}
      >
        <span
          style={{
            display: "flex",
            height: 28,
            width: 28,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 6,
            background:
              "linear-gradient(to bottom right, var(--color-primary-500, var(--color-primary-500)), var(--color-blue-600))",
            color: "var(--color-surface)",
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
          }}
        >
          <ListChecks style={{ width: 14, height: 14 }} aria-hidden />
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <h2
            style={{
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: "-0.025em",
              color: "var(--color-text)",
            }}
          >
            {t("pipeline.queue.title")}
          </h2>
          <p
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontSize: 10.5,
              color: "var(--color-text-secondary)",
            }}
          >
            {activeRuns.length > 0 ? (
              <>
                <span
                  style={{
                    fontWeight: 500,
                    color: "var(--color-primary-700, var(--color-primary-700))",
                  }}
                >
                  {activeRuns.length}
                </span>{" "}
                {t("pipeline.queue.active")} · {total} {t("pipeline.queue.total")}
              </>
            ) : (
              <>{total} {t("pipeline.queue.total")}</>
            )}
          </p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label={t("pipeline.queue.close")}
            className="tqp-close-btn"
          >
            <X style={{ width: 16, height: 16 }} />
          </button>
        )}
      </header>


      {/* Tabs */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          padding: "12px 12px 0",
        }}
      >
        <TabButton
          active={tab === "active"}
          onClick={() => setTab("active")}
          icon={<Radio style={{ width: 12, height: 12 }} />}
          label={t("pipeline.queue.tabActive")}
          count={activeRuns.length}
          pulse={activeRuns.length > 0}
        />
        <TabButton
          active={tab === "recent"}
          onClick={() => setTab("recent")}
          icon={<Inbox style={{ width: 12, height: 12 }} />}
          label={t("pipeline.queue.tabRecent")}
          count={recentRuns.length}
        />
        <TabButton
          active={tab === "failed"}
          onClick={() => setTab("failed")}
          icon={<AlertTriangle style={{ width: 12, height: 12 }} />}
          label={t("pipeline.queue.tabFailed")}
          count={failedRuns.length}
          pulse={failedRuns.length > 0 && tab !== "failed"}
        />
        <Link
          to="/pipeline"
          className="tqp-view-all"
          title={t("pipeline.queue.openPipeline")}
        >
          <span>{t("pipeline.queue.viewAll")}</span>
          <ChevronRight style={{ width: 12, height: 12 }} />
        </Link>
      </div>

      {/* Body */}
      <div
        style={{
          minHeight: 0,
          flex: 1,
          overflowY: "auto",
          padding: "8px 8px 12px",
        }}
      >
        {isLoading && runs.length === 0 ? (
          <LoadingSkeleton />
        ) : isError ? (
          <ErrorState t={t} />
        ) : visible.length === 0 ? (
          <EmptyState message={emptyMessage} t={t} />
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

      {/* Footer */}
      <footer
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderTop: "1px solid var(--color-bg-muted)",
          padding: "8px 16px",
          fontSize: 10,
          color: "var(--color-text-muted)",
        }}
      >
        <Activity style={{ width: 12, height: 12 }} aria-hidden />
        <span
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {updatedAt ? `${t("pipeline.queue.synced")} ${updatedAt}` : t("pipeline.queue.syncing")}
        </span>
        <span
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <Layers3 style={{ width: 12, height: 12 }} aria-hidden />
          <span>{t("pipeline.queue.live")}</span>
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

function TabButton({
  active,
  onClick,
  icon,
  label,
  count,
  pulse,
}: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="tqp-tab-btn"
      style={
        active
          ? {
              backgroundColor: "var(--color-text)",
              color: "var(--color-surface)",
              boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            }
          : { color: "var(--color-text-strong)" }
      }
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = "var(--color-bg-muted)";
          e.currentTarget.style.color = "var(--color-text)";
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = "";
          e.currentTarget.style.color = "var(--color-text-strong)";
        }
      }}
    >
      <span style={{ color: active ? "var(--color-surface)" : "var(--color-text-muted)" }}>{icon}</span>
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
            backgroundColor: active ? "var(--color-surface)" : "var(--color-border)",
            color: active ? "var(--color-surface)" : "var(--color-text-strong)",
          }}
        >
          {count}
        </span>
      )}
      {pulse && !active && (
        <span
          style={{
            position: "relative",
            marginLeft: 2,
            display: "flex",
            width: 6,
            height: 6,
          }}
        >
          <span
            style={{
              position: "absolute",
              display: "inline-flex",
              height: "100%",
              width: "100%",
              animation: "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite",
              borderRadius: "50%",
              backgroundColor: "var(--color-primary-400)",
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
              backgroundColor: "var(--color-primary-600, var(--color-primary-600))",
            }}
          />
        </span>
      )}
    </button>
  );
}

function LoadingSkeleton() {
  return (
    <ul
      style={{ display: "flex", flexDirection: "column", gap: 8, padding: "0 4px" }}
    >
      {Array.from({ length: 3 }).map((_, i) => (
        <li
          key={i}
          style={{
            borderRadius: 8,
            border: "1px solid var(--color-bg-muted)",
            backgroundColor: "var(--color-surface)",
            padding: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Skeleton variant="circle" width={10} height={10} />
            <Skeleton width={64} height={10} />
            <Skeleton
              variant="pill"
              width={40}
              height={12}
              style={{ marginLeft: "auto" }}
            />
          </div>
          <Skeleton width="75%" height={8} style={{ marginTop: 8 }} />
          <Skeleton width="100%" height={6} style={{ marginTop: 8 }} />
        </li>
      ))}
    </ul>
  );
}

type TFn = (key: string) => string;

function ErrorState({ t }: { t: TFn }) {
  return (
    <div
      style={{
        margin: "24px 12px 0",
        borderRadius: 8,
        border: "1px solid var(--color-error-100)",
        backgroundColor: "var(--color-error-bg)",
        padding: 16,
        textAlign: "center",
      }}
    >
      <p style={{ fontSize: 11.5, fontWeight: 500, color: "var(--color-error-text)" }}>
        {t("pipeline.queue.loadError")}
      </p>
      <p
        style={{
          marginTop: 4,
          fontSize: 10.5,
          lineHeight: 1.625,
          color: "var(--color-error-text)",
        }}
      >
        {t("pipeline.queue.loadErrorHint")}
      </p>
    </div>
  );
}

function EmptyState({ message: msg, t }: { message: string; t: TFn }) {
  return (
    <div
      style={{
        margin: "40px 12px 0",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        textAlign: "center",
      }}
    >
      <span
        style={{
          display: "flex",
          height: 40,
          width: 40,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "50%",
          backgroundColor: "var(--color-bg-muted)",
          color: "var(--color-text-muted)",
        }}
      >
        <Inbox style={{ width: 16, height: 16 }} aria-hidden />
      </span>
      <p
        style={{ marginTop: 12, fontSize: 12, fontWeight: 500, color: "var(--color-text-strong)" }}
      >
        {msg}
      </p>
      <p
        style={{
          marginTop: 4,
          maxWidth: 220,
          fontSize: 10.5,
          lineHeight: 1.625,
          color: "var(--color-text-secondary)",
        }}
      >
        {t("pipeline.queue.dropHint")}
      </p>
    </div>
  );
}
