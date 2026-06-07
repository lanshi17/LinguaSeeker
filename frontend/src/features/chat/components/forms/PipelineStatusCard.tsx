"use client";

import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils/cn";

interface PipelineStatusCardProps {
  runId: string;
  status: string;
  phases?: Record<string, { status: string; duration_seconds?: number | null }>;
}

const STATUS_VARIANT: Record<string, "default" | "info" | "success" | "error"> = {
  queued: "default",
  running: "info",
  completed: "success",
  failed: "error",
};

const PHASE_LABELS: Record<string, string> = {
  phase_1: "Acquisition",
  phase_2: "Extraction",
  phase_3: "Standardization",
};

const PHASE_STATUS_ICON: Record<string, string> = {
  completed: "✓",
  running: "●",
  failed: "✕",
  queued: "○",
};

/**
 * Compact pipeline status card rendered inside a chat bubble.
 * Shows 3-phase progress with status icons.
 */
export function PipelineStatusCard({
  runId,
  status,
  phases,
}: PipelineStatusCardProps) {
  const phaseOrder = ["phase_1", "phase_2", "phase_3"];

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-xs text-gray-500">
          {runId.slice(0, 8)}...
        </span>
        <Badge variant={STATUS_VARIANT[status] ?? "default"}>
          {status === "running" && (
            <Spinner size="sm" className="mr-1 inline h-3 w-3" />
          )}
          {status}
        </Badge>
      </div>

      {phases && (
        <div className="flex items-center gap-1">
          {phaseOrder.map((phaseId, i) => {
            const phase = phases[phaseId];
            if (!phase) return null;

            return (
              <div key={phaseId} className="flex items-center">
                <div
                  className={cn(
                    "flex h-7 items-center gap-1 rounded-full px-2 text-xs font-medium",
                    phase.status === "completed" &&
                      "bg-green-100 text-green-700",
                    phase.status === "running" && "bg-blue-100 text-blue-700",
                    phase.status === "failed" && "bg-red-100 text-red-700",
                    phase.status === "queued" && "bg-gray-100 text-gray-500",
                  )}
                >
                  <span>{PHASE_STATUS_ICON[phase.status] ?? "○"}</span>
                  <span>{PHASE_LABELS[phaseId] ?? phaseId}</span>
                  {phase.duration_seconds != null && (
                    <span className="text-[10px] opacity-60">
                      {phase.duration_seconds.toFixed(0)}s
                    </span>
                  )}
                </div>
                {i < phaseOrder.length - 1 && (
                  <div className="mx-0.5 h-px w-2 bg-gray-300" />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
