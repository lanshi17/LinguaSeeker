"use client";

import { usePipelineStatus } from "../hooks/usePipelineStatus";
import { usePhaseTimeline } from "../hooks/usePhaseTimeline";
import { PhaseTimeline } from "./PhaseTimeline";
import { PhaseDetailCard, PhaseDetailCardSkeleton } from "./PhaseDetailCard";
import { Spinner } from "@/components/ui/Spinner";
import { LivePulse } from "@/components/ui/LivePulse";
import { PageHeader } from "@/components/layout/PageHeader";
import { RunHistory } from "./RunHistory";
import { formatDuration, formatTimestamp } from "@/lib/utils/format";
import { useElapsedSeconds } from "@/lib/hooks/useElapsedSeconds";
import type { ProcessingStatus } from "../types/pipeline";
import { cn } from "@/lib/utils/cn";

interface PipelineStatusViewProps {
  runId: string;
}

const TERMINAL: ReadonlyArray<ProcessingStatus> = [
  "completed",
  "failed",
  "cancelled",
];

export function PipelineStatusView({ runId }: PipelineStatusViewProps) {
  const { data, isLoading, error, isFetching } = usePipelineStatus(runId);
  const timelineSteps = usePhaseTimeline(data);
  const isLive = data ? !TERMINAL.includes(data.pipeline_status) : false;
  const elapsed = useElapsedSeconds(isLive ? data?.started_at : data?.completed_at);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Pipeline Status"
          description={
            <span className="font-mono text-gray-500">{runId}</span>
          }
          actions={
            <span className="inline-flex items-center gap-2 rounded-full bg-primary-50 px-3 py-1 text-xs font-medium text-primary-700 ring-1 ring-primary-200">
              <LivePulse tone="primary" />
              Loading
            </span>
          }
        />
        <div className="rounded-xl border border-dashed border-gray-200 bg-white/60 p-6">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner size="sm" />
            Connecting to pipeline service…
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <PhaseDetailCardSkeleton key={i} index={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Pipeline Status"
          description={<span className="font-mono text-gray-500">{runId}</span>}
        />
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            Failed to load pipeline status.
          </p>
          <p className="mt-1 text-xs text-red-700">
            The run may have expired or the backend is unavailable. Check the
            connection indicator and retry.
          </p>
        </div>
        <RunHistory />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline Status"
        description={
          <span className="flex items-center gap-2">
            <span className="text-gray-500">Run</span>
            <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[12px] text-gray-800">
              {runId}
            </code>
            {isFetching && isLive && (
              <span className="text-[11px] text-gray-400">· syncing…</span>
            )}
          </span>
        }
        actions={
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ring-1",
              isLive
                ? "bg-primary-50 text-primary-700 ring-primary-200"
                : data.pipeline_status === "completed"
                  ? "bg-success-50 text-success-700 ring-success-200"
                  : data.pipeline_status === "failed"
                    ? "bg-red-50 text-red-700 ring-red-200"
                    : "bg-gray-100 text-gray-600 ring-gray-200",
            )}
          >
            {isLive ? <LivePulse tone="primary" /> : null}
            {data.pipeline_status}
            {isLive && (
              <span className="ml-1 font-mono tabular-nums text-primary-700/80">
                {formatDuration(elapsed)}
              </span>
            )}
          </span>
        }
      />

      <div className="grid gap-3 md:grid-cols-3">
        <MetaTile
          label="Source document"
          value={data.source_document_id}
          mono
        />
        <MetaTile label="Started" value={formatTimestamp(data.started_at)} mono />
        <MetaTile
          label={isLive ? "Elapsed" : "Total time"}
          value={formatDuration(data.elapsed_seconds ?? elapsed)}
          mono
        />
      </div>

      <div className="flex justify-center rounded-xl border border-gray-100 bg-white py-4">
        <PhaseTimeline steps={timelineSteps} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {timelineSteps.map((step, i) => {
          const phase = data.phases[step.phaseId];
          if (!phase) return <PhaseDetailCardSkeleton key={step.phaseId} index={i} />;
          return (
            <PhaseDetailCard
              key={step.phaseId}
              phaseId={step.phaseId}
              phase={phase}
              index={i}
            />
          );
        })}
      </div>

      {data.error_message && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <span className="font-semibold">
            {data.error_phase
              ? `Phase ${data.error_phase} failed:`
              : "Pipeline failed:"}
          </span>{" "}
          {data.error_message}
        </div>
      )}

      <RunHistory />
    </div>
  );
}

function MetaTile({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-md border border-gray-100 bg-gray-50/60 px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-gray-500">
        {label}
      </div>
      <div
        className={cn(
          "mt-0.5 truncate text-sm text-gray-900",
          mono && "font-mono tabular-nums",
        )}
        title={value}
      >
        {value}
      </div>
    </div>
  );
}
