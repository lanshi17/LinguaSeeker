import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Copy, FileText, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { LivePulse } from "@/components/ui/LivePulse";
import { useI18n } from "@/lib/i18n";
import { useElapsedSeconds } from "@/lib/hooks/useElapsedSeconds";
import { formatDuration, formatRelative, formatTimestamp } from "@/lib/utils/format";
import type { PipelineRunSummary, ProcessingStatus } from "../types/pipeline";

interface RunListItemProps {
  run: PipelineRunSummary;
  index: number;
}

const STATUS_TONE: Record<
  ProcessingStatus,
  "default" | "info" | "success" | "error" | "warning"
> = {
  pending: "default",
  running: "info",
  completed: "success",
  failed: "error",
  skipped: "default",
};

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

const statusDotColor = (status: ProcessingStatus): string => {
  switch (status) {
    case "completed":
      return "var(--color-success-600)";
    case "failed":
      return "var(--color-error-text)";
    case "running":
      return "var(--color-primary-600)";
    default:
      return "var(--color-text-muted)";
  }
};

const progressBarBg = (
  isLive: boolean,
  status: ProcessingStatus,
): string => {
  if (isLive) return "var(--color-primary-600, #0891b2)";
  if (status === "completed") return "var(--color-success-500, #22c55e)";
  if (status === "failed") return "var(--color-error-text)";
  return "var(--color-text-muted)";
};

export function RunListItem({ run, index }: RunListItemProps) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const isLive = run.pipeline_status === "running" || run.pipeline_status === "pending";
  const liveElapsed = useElapsedSeconds(isLive ? run.started_at : undefined);
  const terminalDuration =
    run.started_at && run.completed_at
      ? (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000
      : null;

  const completedPhases = run.completed_phases ?? 0;
  const totalPhases = run.total_phases ?? 4;
  const progress = Math.min(100, Math.max(0, (completedPhases / totalPhases) * 100));

  const durationSeconds = run.elapsed_seconds ?? (isLive ? liveElapsed : terminalDuration);

  const STATUS_LABEL: Record<ProcessingStatus, string> = {
    pending: t("pipeline.status.pending"),
    running: t("pipeline.status.running"),
    completed: t("pipeline.status.completed"),
    failed: t("pipeline.status.failed"),
    skipped: t("pipeline.status.skipped"),
  };

  async function handleCopy(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(run.processing_run_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }

  return (
      <Link
        to={`/pipeline/${run.processing_run_id}`}
        className={`rli-link stagger-in`}
        style={{ animationDelay: `${Math.min(index, 12) * 40}ms` }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div style={{ marginTop: 4, display: "flex", width: 24, flexShrink: 0, justifyContent: "center" }}>
            {isLive ? (
              <LivePulse tone={PULSE_TONE[run.pipeline_status]} label={run.pipeline_status} />
            ) : (
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  backgroundColor: statusDotColor(run.pipeline_status),
                }}
                aria-hidden
              />
            )}
          </div>

          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <div style={{ display: "flex", minWidth: 0, alignItems: "center", gap: 8 }}>
                <FileText style={{ width: 14, height: 14, flexShrink: 0, color: "var(--color-text-muted)" }} aria-hidden />
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    fontFamily: "var(--font-mono, monospace)",
                    fontSize: 13,
                    fontWeight: 500,
                    letterSpacing: "-0.025em",
                    color: "var(--color-text)",
                  }}
                  title={run.processing_run_id}
                >
                  {run.processing_run_id}
                </span>
                <button
                  type="button"
                  onClick={handleCopy}
                  aria-label={t("pipeline.copyRunId")}
                  className="rli-copy-btn"
                >
                  {copied ? (
                    <Check style={{ width: 14, height: 14, color: "var(--color-success-600)" }} />
                  ) : (
                    <Copy style={{ width: 14, height: 14 }} />
                  )}
                </button>
              </div>
              <Badge variant={STATUS_TONE[run.pipeline_status]}>
                {STATUS_LABEL[run.pipeline_status]}
              </Badge>
            </div>

            {run.title && (
              <p
                style={{
                  marginTop: 6,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  fontSize: 12,
                  color: "var(--color-text-strong)",
                }}
                title={run.title}
              >
                {run.title}
              </p>
            )}
            {run.current_phase && isLive && (
              <p style={{ marginTop: 4, fontSize: 12, color: "var(--color-primary-700, var(--color-primary-700))" }}>
                <Loader2 style={{ marginRight: 4, display: "inline", width: 12, height: 12 }} className="spin" />
                {run.current_phase}
              </p>
            )}

            <div
              style={{
                marginTop: 10,
                display: "flex",
                alignItems: "center",
                gap: 12,
                fontSize: 11,
                color: "var(--color-text-secondary)",
              }}
            >
              <span style={{ fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums" }}>
                {formatRelative(run.started_at)}
              </span>
              <span style={{ color: "var(--color-text-muted)" }}>·</span>
              <span style={{ fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums" }}>
                {formatDuration(durationSeconds)}
              </span>
              <span
                style={{
                  marginLeft: "auto",
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 10,
                  fontVariantNumeric: "tabular-nums",
                  color: "var(--color-text-muted)",
                }}
              >
                {completedPhases}/{totalPhases} {t("pipeline.phases")}
              </span>
            </div>

            <div
              style={{
                marginTop: 6,
                height: 4,
                overflow: "hidden",
                borderRadius: 9999,
                backgroundColor: "var(--color-bg-muted)",
              }}
            >
              <div
                className={isLive ? "progress-stripe" : undefined}
                style={{
                  height: "100%",
                  borderRadius: 9999,
                  transition: "width 500ms ease-out",
                  backgroundColor: progressBarBg(isLive, run.pipeline_status),
                  width: `${progress}%`,
                }}
              />
            </div>

            <div className="rli-reveal" style={{ marginTop: 4 }}>
              {t("pipeline.started")} {formatTimestamp(run.started_at)}
              {run.completed_at && ` · ${t("pipeline.completedAt")} ${formatTimestamp(run.completed_at)}`}
            </div>
          </div>
        </div>
      </Link>
  );
}
