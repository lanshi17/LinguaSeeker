"use client";

import type { PhaseTimelineStep } from "../types/pipeline";
import { cn } from "@/lib/utils/cn";

interface PhaseTimelineProps {
  steps: PhaseTimelineStep[];
}

const statusStyles: Record<string, string> = {
  queued: "bg-gray-200 text-gray-500",
  running: "bg-blue-100 text-blue-700 animate-pulse",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-400",
};

const connectorStyles: Record<string, string> = {
  completed: "bg-green-400",
  default: "bg-gray-200",
};

export function PhaseTimeline({ steps }: PhaseTimelineProps) {
  return (
    <div className="flex items-center gap-0">
      {steps.map((step, i) => (
        <div key={step.phaseId} className="flex items-center">
          {/* Phase node */}
          <div className="flex flex-col items-center">
            <div
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold",
                statusStyles[step.status] ?? statusStyles.queued,
              )}
            >
              {i + 1}
            </div>
            <span className="mt-2 text-xs font-medium text-gray-600">
              {step.label}
            </span>
            {step.duration != null && (
              <span className="mt-0.5 text-xs text-gray-400">
                {step.duration.toFixed(1)}s
              </span>
            )}
          </div>

          {/* Connector line */}
          {i < steps.length - 1 && (
            <div
              className={cn(
                "mx-2 h-0.5 w-16",
                step.status === "completed"
                  ? connectorStyles.completed
                  : connectorStyles.default,
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}
