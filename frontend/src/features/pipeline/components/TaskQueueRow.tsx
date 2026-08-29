import { Link } from "react-router-dom";
import type { CSSProperties } from "react";
import {
  Check,
  FileText,
  Loader2,
  Clock,
} from "lucide-react";
import { LivePulse } from "@/components/ui/LivePulse";
import { useI18n } from "@/lib/i18n";
import { useElapsedSeconds } from "@/lib/hooks/useElapsedSeconds";
import { formatDuration, formatRelative } from "@/lib/utils/format";
import type { PipelineRunSummary, ProcessingStatus } from "../types/pipeline";

interface TaskQueueRowProps {
  run: PipelineRunSummary;
}

const PULSE_TONE: Record<
  ProcessingStatus,
  "primary" | "success" | "warning" | "error" | "neutral"
> = {
  pending: "neutral",
  running: "primary",
  completed: "success",
  failed: "error",
  skipped: "neutral",
};

const DOT_COLORS: Record<ProcessingStatus, string> = {
  pending: "var(--color-text-muted)",
  running: "var(--color-primary-600)",
  completed: "var(--color-success-600)",
  failed: "var(--color-error-text)",
  skipped: "var(--color-text-muted)",
};

const BADGE_STYLES: Record<ProcessingStatus, CSSProperties> = {
  pending: { backgroundColor: "var(--color-bg-muted)", color: "var(--color-text-strong)" },
  running: { backgroundColor: "var(--color-highlight)", color: "var(--color-primary-700)" },
  completed: { backgroundColor: "var(--color-highlight-green)", color: "var(--color-success-700)" },
  failed: { backgroundColor: "var(--color-error-bg)", color: "var(--color-error-text)" },
  skipped: { backgroundColor: "var(--color-bg-muted)", color: "var(--color-text-secondary)" },
};

const PHASE_BOX_DONE: CSSProperties = {
  display: "inline-flex",
  width: 14,
  height: 14,
  alignItems: "center",
  justifyContent: "center",
  borderRadius: 3,
  backgroundColor: "var(--color-success-100)",
  color: "var(--color-success-600)",
};

const PHASE_BOX_ACTIVE: CSSProperties = {
  display: "inline-flex",
  width: 14,
  height: 14,
  alignItems: "center",
  justifyContent: "center",
  borderRadius: 3,
  backgroundColor: "var(--color-highlight)",
  color: "var(--color-primary-600)",
};

const PHASE_BOX_IDLE: CSSProperties = {
  display: "inline-flex",
  width: 14,
  height: 14,
  alignItems: "center",
  justifyContent: "center",
  borderRadius: 3,
  backgroundColor: "var(--color-bg-muted)",
  color: "var(--color-text-muted)",
};

export function TaskQueueRow({ run }: TaskQueueRowProps) {
  const { t } = useI18n();
  const isLive = run.pipeline_status === "running" || run.pipeline_status === "pending";
  const liveElapsed = useElapsedSeconds(isLive ? run.started_at : undefined);

  const completedPhases = run.completed_phases ?? 0;
  const totalPhases = run.total_phases ?? 4;

  const elapsed =
    run.elapsed_seconds ??
    (isLive
      ? liveElapsed
      : run.started_at && run.completed_at
        ? (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000
        : null);

  const subtitle = run.title ?? run.current_phase ?? null;

  const STATUS_LABEL: Record<ProcessingStatus, string> = {
    pending: t("pipeline.status.queued"),
    running: t("pipeline.status.running"),
    completed: t("pipeline.status.done"),
    failed: t("pipeline.status.failed"),
    skipped: t("pipeline.status.skipped"),
  };

  return (
      <Link
        to={`/pipeline/${run.processing_run_id}`}
        className="tqr-link"
      >
        {/* Header: status dot + run ID + badge */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ display: "flex", width: 16, height: 16, flexShrink: 0, alignItems: "center", justifyContent: "center" }}>
            {isLive ? (
              <LivePulse tone={PULSE_TONE[run.pipeline_status]} />
            ) : (
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: DOT_COLORS[run.pipeline_status],
                }}
                aria-hidden
              />
            )}
          </span>
          <span
            style={{
              minWidth: 0,
              flex: 1,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontFamily: "var(--font-mono)",
              fontSize: 11.5,
              fontWeight: 500,
              letterSpacing: "-0.01em",
              color: "var(--color-code-text)",
            }}
            title={run.processing_run_id}
          >
            {run.processing_run_id.slice(0, 8)}
          </span>
          <span
            style={{
              flexShrink: 0,
              borderRadius: 9999,
              padding: "1px 6px",
              fontSize: 10,
              fontWeight: 500,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              ...BADGE_STYLES[run.pipeline_status],
            }}
          >
            {STATUS_LABEL[run.pipeline_status]}
          </span>
        </div>

        {/* Subtitle: title or current phase */}
        {subtitle && (
          <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 6, paddingLeft: 24 }}>
            {run.pipeline_status === "running" && run.current_phase ? (
              <>
                <Loader2 style={{ width: 12, height: 12, flexShrink: 0, color: "var(--color-primary-600)", animation: "spin 1s linear infinite" }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 11, color: "var(--color-primary-700)" }}>
                  {run.current_phase}
                </span>
              </>
            ) : (
              <>
                <FileText style={{ width: 12, height: 12, flexShrink: 0, color: "var(--color-text-muted)" }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 11, color: "var(--color-text-strong)" }} title={subtitle}>
                  {subtitle}
                </span>
              </>
            )}
          </div>
        )}

        {/* Phase rail */}
        <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8, paddingLeft: 24 }}>
          <div style={{ display: "flex", height: 16, alignItems: "center", gap: 2 }}>
            {Array.from({ length: totalPhases }).map((_, i) => {
              const done = i < completedPhases;
              const active = i === completedPhases && isLive;
              const boxStyle = done ? PHASE_BOX_DONE : active ? PHASE_BOX_ACTIVE : PHASE_BOX_IDLE;
              return (
                <span key={i} style={boxStyle}>
                  {done ? (
                    <Check style={{ width: 8, height: 8 }} strokeWidth={3} />
                  ) : active ? (
                    <Loader2 style={{ width: 8, height: 8, animation: "spin 1s linear infinite" }} />
                  ) : (
                    <span style={{ width: 4, height: 4, borderRadius: "50%", backgroundColor: "currentColor" }} />
                  )}
                </span>
              );
            })}
          </div>
          <span style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            fontVariantNumeric: "tabular-nums",
            color: "var(--color-text-muted)",
          }}>
            <Clock style={{ width: 10, height: 10 }} aria-hidden />
            {isLive ? formatRelative(run.started_at) : formatDuration(elapsed)}
          </span>
        </div>
      </Link>
  );
}
