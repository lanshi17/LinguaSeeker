import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Copy, FileText, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { LivePulse } from "@/components/ui/LivePulse";
import { useElapsedSeconds } from "@/lib/hooks/useElapsedSeconds";
import { formatDuration, formatRelative, formatTimestamp } from "@/lib/utils/format";
import type { PipelineRunSummary, ProcessingStatus } from "../types/pipeline";

interface RunListItemProps {
  run: PipelineRunSummary;
  index: number;
}

const STATUS_LABEL: Record<ProcessingStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  skipped: "Skipped",
};

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
      return "#22c55e";
    case "failed":
      return "#ef4444";
    case "skipped":
      return "#9ca3af";
    case "pending":
      return "#d1d5db";
    default:
      return "#9ca3af";
  }
};

const progressBarBg = (
  isLive: boolean,
  status: ProcessingStatus,
): string => {
  if (isLive) return "linear-gradient(to right, #38bdf8, #0891b2)";
  if (status === "completed") return "#22c55e";
  if (status === "failed") return "#f87171";
  return "#d1d5db";
};

export function RunListItem({ run, index }: RunListItemProps) {
  const [copied, setCopied] = useState(false);
  const isLive = run.pipeline_status === "running" || run.pipeline_status === "pending";
  const liveElapsed = useElapsedSeconds(isLive ? run.started_at : undefined);
  const terminalDuration =
    run.started_at && run.completed_at
      ? (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000
      : null;

  const completedPhases = run.completed_phases ?? 0;
  const totalPhases = run.total_phases ?? 3;
  const progress = Math.min(100, Math.max(0, (completedPhases / totalPhases) * 100));

  const durationSeconds = run.elapsed_seconds ?? (isLive ? liveElapsed : terminalDuration);

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
    <>
      <style>{`
        .rli-link {
          display: block;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
          background-color: #fff;
          padding: 16px;
          box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05);
          text-decoration: none;
          color: inherit;
          transition: all 200ms ease-out;
        }
        .rli-link:hover {
          transform: translateY(-2px);
          border-color: #7dd3fc;
          box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);
        }
        .rli-link:focus-visible {
          outline: 2px solid #0891b2;
          outline-offset: 2px;
        }
        .rli-reveal {
          overflow: hidden;
          font-size: 10px;
          font-family: var(--font-mono, monospace);
          font-variant-numeric: tabular-nums;
          color: #9ca3af;
          max-height: 0;
          opacity: 0;
          transition: all 200ms;
        }
        .rli-link:hover .rli-reveal {
          max-height: 16px;
          opacity: 1;
        }
        .rli-copy-btn {
          border-radius: 4px;
          padding: 4px;
          color: #9ca3af;
          transition: color 150ms, background-color 150ms;
          border: none;
          background: none;
          cursor: pointer;
        }
        .rli-copy-btn:hover {
          background-color: #f3f4f6;
          color: #0e7490;
        }
        .rli-copy-btn:focus-visible {
          outline: 2px solid #0891b2;
          outline-offset: 2px;
        }
      `}</style>
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
                <FileText style={{ width: 14, height: 14, flexShrink: 0, color: "#9ca3af" }} aria-hidden />
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    fontFamily: "var(--font-mono, monospace)",
                    fontSize: 13,
                    fontWeight: 500,
                    letterSpacing: "-0.025em",
                    color: "#111827",
                  }}
                  title={run.processing_run_id}
                >
                  {run.processing_run_id}
                </span>
                <button
                  type="button"
                  onClick={handleCopy}
                  aria-label="Copy run ID"
                  className="rli-copy-btn"
                >
                  {copied ? (
                    <Check style={{ width: 14, height: 14, color: "#16a34a" }} />
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
                  color: "#4b5563",
                }}
                title={run.title}
              >
                {run.title}
              </p>
            )}
            {run.current_phase && isLive && (
              <p style={{ marginTop: 4, fontSize: 12, color: "#0e7490" }}>
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
                color: "#6b7280",
              }}
            >
              <span style={{ fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums" }}>
                {formatRelative(run.started_at)}
              </span>
              <span style={{ color: "#d1d5db" }}>·</span>
              <span style={{ fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums" }}>
                {formatDuration(durationSeconds)}
              </span>
              <span
                style={{
                  marginLeft: "auto",
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 10,
                  fontVariantNumeric: "tabular-nums",
                  color: "#9ca3af",
                }}
              >
                {completedPhases}/{totalPhases} phases
              </span>
            </div>

            <div
              style={{
                marginTop: 6,
                height: 4,
                overflow: "hidden",
                borderRadius: 9999,
                backgroundColor: "#f3f4f6",
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
              Started {formatTimestamp(run.started_at)}
              {run.completed_at && ` · Done ${formatTimestamp(run.completed_at)}`}
            </div>
          </div>
        </div>
      </Link>
    </>
  );
}
