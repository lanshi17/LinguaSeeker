
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

interface PipelineStatusViewProps {
  runId: string;
}

const NON_LIVE: ReadonlyArray<ProcessingStatus> = [
  "completed",
  "failed",
  "skipped",
];

const statusBadgeStyles = (
  status: ProcessingStatus,
  isLive: boolean,
): React.CSSProperties => {
  const base: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    borderRadius: 9999,
    padding: "4px 12px",
    fontSize: 12,
    fontWeight: 500,
    borderWidth: 1,
    borderStyle: "solid",
  };
  if (isLive) {
    return { ...base, backgroundColor: "#ecfeff", color: "#0e7490", borderColor: "#a5f3fc" };
  }
  if (status === "completed") {
    return { ...base, backgroundColor: "#f0fdf4", color: "#15803d", borderColor: "#bbf7d0" };
  }
  if (status === "failed") {
    return { ...base, backgroundColor: "#fef2f2", color: "#b91c1c", borderColor: "#fecaca" };
  }
  return { ...base, backgroundColor: "#f3f4f6", color: "#4b5563", borderColor: "#e5e7eb" };
};

export function PipelineStatusView({ runId }: PipelineStatusViewProps) {
  const { data, isLoading, error, isFetching } = usePipelineStatus(runId);
  const timelineSteps = usePhaseTimeline(data);
  const isLive = data ? !NON_LIVE.includes(data.pipeline_status) : false;
  // For terminal runs, compute duration from start to completion; for live, use real-time timer
  const terminalDuration =
    data?.started_at && data?.completed_at
      ? (new Date(data.completed_at).getTime() - new Date(data.started_at).getTime()) / 1000
      : null;
  const liveElapsed = useElapsedSeconds(isLive ? data?.started_at : undefined);
  const elapsed = isLive ? liveElapsed : terminalDuration;

  if (isLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <style>{`
          @media (min-width: 768px) {
            .psv-grid { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }
          }
        `}</style>
        <PageHeader
          title="Pipeline Status"
          description={
            <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#6b7280" }}>{runId}</span>
          }
          actions={
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                borderRadius: 9999,
                backgroundColor: "#ecfeff",
                padding: "4px 12px",
                fontSize: 12,
                fontWeight: 500,
                color: "#0e7490",
                border: "1px solid #a5f3fc",
              }}
            >
              <LivePulse tone="primary" />
              Loading
            </span>
          }
        />
        <div
          style={{
            borderRadius: 12,
            border: "1px dashed #e5e7eb",
            backgroundColor: "rgba(255,255,255,0.6)",
            padding: 24,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, color: "#6b7280" }}>
            <Spinner size="sm" />
            Connecting to pipeline service…
          </div>
        </div>
        <div className="psv-grid" style={{ display: "grid", gap: 16 }}>
          {[0, 1, 2].map((i) => (
            <PhaseDetailCardSkeleton key={i} index={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <PageHeader
          title="Pipeline Status"
          description={
            <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#6b7280" }}>{runId}</span>
          }
        />
        <div
          style={{
            borderRadius: 8,
            border: "1px solid #fecaca",
            backgroundColor: "#fef2f2",
            padding: 24,
            textAlign: "center",
          }}
        >
          <p style={{ fontSize: 14, fontWeight: 500, color: "#991b1b" }}>
            Failed to load pipeline status.
          </p>
          <p style={{ marginTop: 4, fontSize: 12, color: "#b91c1c" }}>
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
    <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <style>{`
        @media (min-width: 768px) {
          .psv-grid { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }
        }
      `}</style>
      <PageHeader
        title="Pipeline Status"
        description={
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "#6b7280" }}>Run</span>
            <code
              style={{
                borderRadius: 4,
                backgroundColor: "#f3f4f6",
                padding: "2px 6px",
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 12,
                color: "#1f2937",
              }}
            >
              {runId}
            </code>
            {isFetching && isLive && (
              <span style={{ fontSize: 11, color: "#9ca3af" }}>· syncing…</span>
            )}
          </span>
        }
        actions={
          <span style={statusBadgeStyles(data.pipeline_status, isLive)}>
            {isLive ? <LivePulse tone="primary" /> : null}
            {data.pipeline_status}
            {isLive && (
              <span
                style={{
                  marginLeft: 4,
                  fontFamily: "var(--font-mono, monospace)",
                  fontVariantNumeric: "tabular-nums",
                  color: "rgba(14,116,144,0.8)",
                }}
              >
                {formatDuration(elapsed)}
              </span>
            )}
          </span>
        }
      />

      <div className="psv-grid" style={{ display: "grid", gap: 12 }}>
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

      <div
        style={{
          display: "flex",
          justifyContent: "center",
          borderRadius: 12,
          border: "1px solid #f3f4f6",
          backgroundColor: "#fff",
          padding: "16px 0",
        }}
      >
        <PhaseTimeline steps={timelineSteps} />
      </div>

      <div className="psv-grid" style={{ display: "grid", gap: 16 }}>
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
        <div
          style={{
            borderRadius: 8,
            border: "1px solid #fecaca",
            backgroundColor: "#fef2f2",
            padding: 16,
            fontSize: 14,
            color: "#991b1b",
          }}
        >
          <span style={{ fontWeight: 600 }}>
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
    <div
      style={{
        borderRadius: 6,
        border: "1px solid #f3f4f6",
        backgroundColor: "rgba(249,250,251,0.6)",
        padding: "8px 12px",
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "#6b7280",
        }}
      >
        {label}
      </div>
      <div
        style={{
          marginTop: 2,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontSize: 14,
          color: "#111827",
          ...(mono
            ? { fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums" }
            : {}),
        }}
        title={value}
      >
        {value}
      </div>
    </div>
  );
}
