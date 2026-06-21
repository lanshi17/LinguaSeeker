
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { LivePulse } from "@/components/ui/LivePulse";
import { cn } from "@/lib/utils/cn";
import {
  Check,
  Circle,
  CircleX,
  Clock,
  SkipForward,
} from "lucide-react";

interface PipelineStatusCardProps {
  runId: string;
  status: string;
  phases?: Record<string, { status: string; duration_seconds?: number | null }>;
}

const STATUS_VARIANT: Record<string, "default" | "info" | "success" | "error" | "warning"> = {
  pending: "default",
  running: "info",
  completed: "success",
  failed: "error",
  cancelled: "default",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

interface PhaseMeta {
  id: string;
  label: string;
  description: string;
}

const PHASES: PhaseMeta[] = [
  {
    id: "phase_1",
    label: "Acquisition",
    description: "Fetching and digitising the literature source",
  },
  {
    id: "phase_2",
    label: "Extraction",
    description: "Cross-lingual dual extraction and fusion",
  },
  {
    id: "phase_3",
    label: "Standardisation",
    description: "Entity normalisation and knowledge alignment",
  },
  {
    id: "phase_4",
    label: "Review",
    description: "Expert-in-the-loop visualisation and feedback",
  },
];

const PHASE_STATUS_STYLES: Record<string, string> = {
  pending: "bg-gray-50 text-gray-500 border-gray-200",
  running: "bg-blue-50 text-blue-700 border-blue-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  skipped: "bg-gray-50 text-gray-400 border-gray-200",
};

function PhaseIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <Check className="h-3.5 w-3.5" />;
    case "running":
      return <LivePulse tone="primary" label="Phase running" />;
    case "failed":
      return <CircleX className="h-3.5 w-3.5" />;
    case "skipped":
      return <SkipForward className="h-3.5 w-3.5" />;
    default:
      return <Circle className="h-3.5 w-3.5" />;
  }
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

/**
 * Pipeline progress card rendered inside a chat bubble.
 *
 * Shows:
 * - Run ID + status badge (with live pulse while running)
 * - Per-phase progress pills with icon, label, and duration
 * - Elapsed wall-clock time that ticks every second while running
 * - A subtle hint line that rotates based on the current phase
 */
export function PipelineStatusCard({
  runId,
  status,
  phases,
}: PipelineStatusCardProps) {
  const isRunning = status === "running" || status === "pending";

  // Seed offset: total duration of completed phases reported by the backend.
  // Captured on mount so we don't double-count as `phases` updates stream in.
  const [seededOffset] = useState(() => {
    if (!phases) return 0;
    return Object.values(phases).reduce((acc, p) => {
      return typeof p.duration_seconds === "number"
        ? acc + Math.max(0, Math.floor(p.duration_seconds))
        : acc;
    }, 0);
  });

  // Ticks only while running; when the pipeline is already finished the
  // rendered elapsed equals the captured offset.
  const [extraSeconds, setExtraSeconds] = useState(0);
  useEffect(() => {
    if (!isRunning) return;
    const id = window.setInterval(() => {
      setExtraSeconds((s) => s + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, [isRunning]);

  const elapsed = seededOffset + extraSeconds;

  const runningPhase = PHASES.find((p) => phases?.[p.id]?.status === "running");
  const hint =
    status === "completed"
      ? "All phases finished. Evidence cards are ready for review."
      : status === "failed"
        ? "A phase failed. Check logs for details."
        : runningPhase
          ? `Now: ${runningPhase.description}`
          : "Preparing the pipeline…";

  const completedCount = PHASES.filter(
    (p) => phases?.[p.id]?.status === "completed",
  ).length;
  const progressPct = Math.min(
    100,
    Math.round((completedCount / PHASES.length) * 100),
  );

  return (
    <div className="w-full max-w-md overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      {/* Header: run id + status */}
      <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-mono text-[11px] text-gray-400">
            {runId.slice(0, 8)}…
          </span>
          {isRunning && <LivePulse tone="primary" />}
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-[11px] text-gray-500">
            <Clock className="h-3 w-3" aria-hidden="true" />
            {formatElapsed(elapsed)}
          </span>
          <Badge variant={STATUS_VARIANT[status] ?? "default"}>
            {STATUS_LABEL[status] ?? status}
          </Badge>
        </div>
      </div>

      {/* Phases */}
      <div className="px-4 pt-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {PHASES.map((phase, i) => {
            const phaseData = phases?.[phase.id];
            const phaseStatus = phaseData?.status ?? "pending";
            const duration = phaseData?.duration_seconds;

            return (
              <div key={phase.id} className="flex items-center gap-1.5">
                <div
                  className={cn(
                    "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11.5px] font-medium transition-colors",
                    PHASE_STATUS_STYLES[phaseStatus] ??
                      PHASE_STATUS_STYLES.pending,
                  )}
                  title={phase.description}
                >
                  <PhaseIcon status={phaseStatus} />
                  <span>{phase.label}</span>
                  {typeof duration === "number" && (
                    <span className="opacity-60">
                      {duration.toFixed(0)}s
                    </span>
                  )}
                </div>
                {i < PHASES.length - 1 && (
                  <div className="h-px w-2 bg-gray-200" aria-hidden="true" />
                )}
              </div>
            );
          })}
        </div>

        {/* Progress bar */}
        <div
          className="mt-3 h-1 w-full overflow-hidden rounded-full bg-gray-100"
          role="progressbar"
          aria-valuenow={progressPct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              status === "failed"
                ? "bg-red-500"
                : status === "completed"
                  ? "bg-emerald-500"
                  : "bg-gradient-to-r from-cyan-500 to-blue-500 progress-stripe",
            )}
            style={{ width: `${status === "completed" ? 100 : progressPct}%` }}
          />
        </div>

        {/* Hint line */}
        <p className="mt-2 pb-3 text-[11.5px] leading-relaxed text-gray-500">
          {hint}
        </p>
      </div>
    </div>
  );
}
