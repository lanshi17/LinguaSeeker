import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { PhaseStatus } from "../types/pipeline";

interface PhaseDetailCardProps {
  phase: PhaseStatus;
}

const STATUS_BADGE_VARIANT: Record<string, "default" | "info" | "success" | "error" | "warning"> = {
  queued: "default",
  running: "info",
  completed: "success",
  failed: "error",
  cancelled: "warning",
};

export function PhaseDetailCard({ phase }: PhaseDetailCardProps) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">
          {phase.phase_id.replace("_", " ").toUpperCase()}
        </h3>
        <Badge variant={STATUS_BADGE_VARIANT[phase.status] ?? "default"}>
          {phase.status}
        </Badge>
      </div>

      {phase.started_at && (
        <p className="mt-2 text-xs text-gray-500">
          Started: {new Date(phase.started_at).toLocaleString()}
        </p>
      )}

      {phase.duration_seconds !== undefined && (
        <p className="text-xs text-gray-500">
          Duration: {phase.duration_seconds.toFixed(1)}s
        </p>
      )}

      {phase.summary && (
        <p className="mt-2 text-sm text-gray-700">{phase.summary}</p>
      )}

      {phase.error && (
        <p className="mt-2 text-sm text-red-600">{phase.error}</p>
      )}
    </Card>
  );
}
