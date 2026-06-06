"use client";

import { usePipelineStatus } from "../hooks/usePipelineStatus";
import { usePhaseTimeline } from "../hooks/usePhaseTimeline";
import { PhaseTimeline } from "./PhaseTimeline";
import { PhaseDetailCard } from "./PhaseDetailCard";
import { Spinner } from "@/components/ui/Spinner";
import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/layout/PageHeader";

interface PipelineStatusViewProps {
  runId: string;
}

export function PipelineStatusView({ runId }: PipelineStatusViewProps) {
  const { data, isLoading, error } = usePipelineStatus(runId);
  const timelineSteps = usePhaseTimeline(data);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-sm text-red-800">
          Failed to load pipeline status. Please try again.
        </p>
      </div>
    );
  }

  if (!data) return null;

  const overallVariant =
    data.pipeline_status === "completed"
      ? "success"
      : data.pipeline_status === "failed"
        ? "error"
        : "info";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline Status"
        description={`Run ID: ${runId}`}
        actions={
          <Badge variant={overallVariant}>{data.pipeline_status}</Badge>
        }
      />

      {/* Visual timeline */}
      <div className="flex justify-center py-4">
        <PhaseTimeline steps={timelineSteps} />
      </div>

      {/* Per-phase detail cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {data.phases.map((phase) => (
          <PhaseDetailCard key={phase.phase_id} phase={phase} />
        ))}
      </div>
    </div>
  );
}
