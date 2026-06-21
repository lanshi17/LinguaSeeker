import { Link } from "react-router-dom";
import {
  Check,
  FileText,
  Loader2,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { LivePulse } from "@/components/ui/LivePulse";
import { useElapsedSeconds } from "@/lib/hooks/useElapsedSeconds";
import { formatDuration, formatRelative } from "@/lib/utils/format";
import type { PipelineRunSummary, ProcessingStatus } from "../types/pipeline";

interface TaskQueueRowProps {
  run: PipelineRunSummary;
}

const STATUS_LABEL: Record<ProcessingStatus, string> = {
  pending: "Queued",
  running: "Running",
  completed: "Done",
  failed: "Failed",
  skipped: "Skipped",
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

const DOT_TONE: Record<ProcessingStatus, string> = {
  pending: "bg-gray-300",
  running: "bg-primary-500",
  completed: "bg-success-500",
  failed: "bg-red-500",
  skipped: "bg-gray-400",
};

export function TaskQueueRow({ run }: TaskQueueRowProps) {
  const isLive = run.pipeline_status === "running" || run.pipeline_status === "pending";
  const liveElapsed = useElapsedSeconds(isLive ? run.started_at : undefined);

  const completedPhases = run.completed_phases ?? 0;
  const totalPhases = run.total_phases ?? 3;

  const elapsed =
    run.elapsed_seconds ??
    (isLive
      ? liveElapsed
      : run.started_at && run.completed_at
        ? (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000
        : null);

  const subtitle = run.title ?? run.current_phase ?? null;

  return (
    <Link
      to={`/pipeline/${run.processing_run_id}`}
      className={cn(
        "group relative block rounded-lg border border-transparent px-3 py-2.5",
        "transition-all duration-150 ease-out",
        "hover:-translate-y-px hover:border-gray-200 hover:bg-white hover:shadow-sm",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600",
      )}
    >
      {/* Header: status dot + run ID + badge */}
      <div className="flex items-center gap-2">
        <span className="flex h-4 w-4 shrink-0 items-center justify-center">
          {isLive ? (
            <LivePulse tone={PULSE_TONE[run.pipeline_status]} />
          ) : (
            <span
              className={cn("h-2 w-2 rounded-full", DOT_TONE[run.pipeline_status])}
              aria-hidden
            />
          )}
        </span>
        <span
          className="min-w-0 flex-1 truncate font-mono text-[11.5px] font-medium tracking-tight text-gray-800"
          title={run.processing_run_id}
        >
          {run.processing_run_id.slice(0, 8)}
        </span>
        <span
          className={cn(
            "shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium uppercase tracking-wide",
            run.pipeline_status === "completed" && "bg-success-50 text-success-700",
            run.pipeline_status === "running" && "bg-primary-50 text-primary-700",
            run.pipeline_status === "failed" && "bg-red-50 text-red-700",
            run.pipeline_status === "pending" && "bg-gray-100 text-gray-600",
            run.pipeline_status === "skipped" && "bg-gray-100 text-gray-500",
          )}
        >
          {STATUS_LABEL[run.pipeline_status]}
        </span>
      </div>

      {/* Subtitle: title or current phase */}
      {subtitle && (
        <div className="mt-1 flex items-center gap-1.5 pl-6">
          {run.pipeline_status === "running" && run.current_phase ? (
            <>
              <Loader2 className="h-3 w-3 shrink-0 animate-spin text-primary-600" />
              <span className="truncate text-[11px] text-primary-700">
                {run.current_phase}
              </span>
            </>
          ) : (
            <>
              <FileText className="h-3 w-3 shrink-0 text-gray-400" />
              <span className="truncate text-[11px] text-gray-600" title={subtitle}>
                {subtitle}
              </span>
            </>
          )}
        </div>
      )}

      {/* Phase rail */}
      <div className="mt-2 flex items-center gap-2 pl-6">
        <div className="flex h-4 items-center gap-0.5">
          {Array.from({ length: totalPhases }).map((_, i) => {
            const done = i < completedPhases;
            const active = i === completedPhases && isLive;
            return (
              <span
                key={i}
                className={cn(
                  "flex h-3.5 w-3.5 items-center justify-center rounded-[4px] border text-[8px]",
                  done && "border-success-300 bg-success-50 text-success-700",
                  active && "border-primary-300 bg-primary-50 text-primary-700",
                  !done && !active && "border-gray-200 bg-white text-gray-400",
                )}
              >
                {done ? (
                  <Check className="h-2 w-2" strokeWidth={3} />
                ) : active ? (
                  <Loader2 className="h-2 w-2 animate-spin" />
                ) : (
                  <span className="h-1 w-1 rounded-full bg-current" />
                )}
              </span>
            );
          })}
        </div>
        <span className="ml-auto flex items-center gap-1 font-mono text-[10px] tabular-nums text-gray-400">
          <Clock className="h-2.5 w-2.5" aria-hidden />
          {isLive ? formatRelative(run.started_at) : formatDuration(elapsed)}
        </span>
      </div>
    </Link>
  );
}
