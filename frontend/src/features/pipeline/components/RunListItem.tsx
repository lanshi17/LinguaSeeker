"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Copy, FileText, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { LivePulse } from "@/components/ui/LivePulse";
import { cn } from "@/lib/utils/cn";
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
  awaiting_review: "Awaiting review",
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
  awaiting_review: "warning",
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
  awaiting_review: "warning",
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
    <Link
      href={`/pipeline/${run.processing_run_id}`}
      className={cn(
        "stagger-in group block rounded-lg border border-gray-200 bg-white p-4 shadow-sm",
        "transition-all duration-200 ease-out",
        "hover:-translate-y-0.5 hover:border-primary-300 hover:shadow-md",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600",
      )}
      style={{ animationDelay: `${Math.min(index, 12) * 40}ms` }}
    >
      <div className="flex items-start gap-3">
        <div className="mt-1 flex w-6 shrink-0 items-center justify-center">
          {isLive ? (
            <LivePulse tone={PULSE_TONE[run.pipeline_status]} label={run.pipeline_status} />
          ) : (
            <span
              className={cn(
                "h-2.5 w-2.5 rounded-full",
                run.pipeline_status === "completed" && "bg-success-500",
                run.pipeline_status === "failed" && "bg-red-500",
                run.pipeline_status === "skipped" && "bg-gray-400",
                run.pipeline_status === "pending" && "bg-gray-300",
                run.pipeline_status === "awaiting_review" && "bg-amber-400",
              )}
              aria-hidden
            />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <FileText className="h-3.5 w-3.5 shrink-0 text-gray-400" aria-hidden />
              <span
                className="truncate font-mono text-[13px] font-medium tracking-tight text-gray-900"
                title={run.processing_run_id}
              >
                {run.processing_run_id}
              </span>
              <button
                type="button"
                onClick={handleCopy}
                aria-label="Copy run ID"
                className={cn(
                  "rounded p-1 text-gray-400 transition-colors",
                  "hover:bg-gray-100 hover:text-primary-700",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600",
                )}
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-success-600" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
            <Badge variant={STATUS_TONE[run.pipeline_status]}>
              {STATUS_LABEL[run.pipeline_status]}
            </Badge>
          </div>

          {run.title && (
            <p className="mt-1.5 truncate text-xs text-gray-600" title={run.title}>
              {run.title}
            </p>
          )}
          {run.current_phase && isLive && (
            <p className="mt-1 text-xs text-primary-700">
              <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />
              {run.current_phase}
            </p>
          )}

          <div className="mt-2.5 flex items-center gap-3 text-[11px] text-gray-500">
            <span className="font-mono tabular-nums">
              {formatRelative(run.started_at)}
            </span>
            <span className="text-gray-300">·</span>
            <span className="font-mono tabular-nums">
              {formatDuration(durationSeconds)}
            </span>
            <span className="ml-auto font-mono text-[10px] tabular-nums text-gray-400">
              {completedPhases}/{totalPhases} phases
            </span>
          </div>

          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-gray-100">
            <div
              className={cn(
                "h-full rounded-full transition-[width] duration-500 ease-out",
                isLive
                  ? "bg-gradient-to-r from-primary-400 to-primary-600 progress-stripe"
                  : run.pipeline_status === "completed"
                    ? "bg-success-500"
                    : run.pipeline_status === "failed"
                      ? "bg-red-400"
                      : "bg-gray-300",
              )}
              style={{ width: `${progress}%` }}
            />
          </div>

          <div
            className={cn(
              "mt-1 overflow-hidden text-[10px] font-mono tabular-nums text-gray-400",
              "max-h-0 opacity-0 transition-all duration-200",
              "group-hover:max-h-4 group-hover:opacity-100",
            )}
          >
            Started {formatTimestamp(run.started_at)}
            {run.completed_at && ` · Done ${formatTimestamp(run.completed_at)}`}
          </div>
        </div>
      </div>
    </Link>
  );
}
