import { STATUS_VARIANT } from "@/lib/constants/statusVariant";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { Badge } from "@/components/ui/Badge";
import { LivePulse } from "@/components/ui/LivePulse";
import { useI18n } from "@/lib/i18n";
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


function getStatusLabel(t: (key: string) => string): Record<string, string> {
  return {
    pending: t("chat.status.queued"),
    running: t("chat.status.running"),
    completed: t("chat.status.completed"),
    failed: t("chat.status.failed"),
    cancelled: t("chat.status.cancelled"),
  };
}

interface PhaseMeta {
  id: string;
  labelKey: string;
  descKey: string;
}

const PHASES: PhaseMeta[] = [
  { id: "phase_1", labelKey: "chat.phase.acquisition", descKey: "chat.phase.acquisitionDesc" },
  { id: "phase_2", labelKey: "chat.phase.parsing", descKey: "chat.phase.parsingDesc" },
  { id: "phase_3", labelKey: "chat.phase.extraction", descKey: "chat.phase.extractionDesc" },
  { id: "phase_4", labelKey: "chat.phase.standardization", descKey: "chat.phase.standardizationDesc" },
  { id: "phase_5", labelKey: "chat.phase.review", descKey: "chat.phase.reviewDesc" },
];

const PHASE_STATUS_STYLES: Record<string, CSSProperties> = {
  pending: { backgroundColor: "var(--color-bg)", color: "var(--color-text-secondary)", borderColor: "var(--color-border)" },
  running: { backgroundColor: "var(--color-running-bg)", color: "var(--color-running-text)", borderColor: "var(--color-running-border)" },
  completed: { backgroundColor: "var(--color-highlight-green)", color: "var(--color-success-text)", borderColor: "var(--color-success-200)" },
  failed: { backgroundColor: "var(--color-error-bg)", color: "var(--color-error-text)", borderColor: "var(--color-error-border)" },
  skipped: { backgroundColor: "var(--color-bg)", color: "var(--color-text-muted)", borderColor: "var(--color-border)" },
};

function PhaseIcon({ status }: { status: string }) {
  const { t } = useI18n();
  switch (status) {
    case "completed":
      return <Check style={{ width: 14, height: 14 }} />;
    case "running":
      return <LivePulse tone="primary" label={t("chat.status.phaseRunning")} />;
    case "failed":
      return <CircleX style={{ width: 14, height: 14 }} />;
    case "skipped":
      return <SkipForward style={{ width: 14, height: 14 }} />;
    default:
      return <Circle style={{ width: 14, height: 14 }} />;
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
  const { t } = useI18n();
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
      ? t("chat.status.allFinished")
      : status === "failed"
        ? t("chat.status.phaseFailedHint")
        : runningPhase
          ? t("chat.status.nowPhase", { desc: t(runningPhase.descKey) })
          : t("chat.status.preparing");

  const completedCount = PHASES.filter(
    (p) => phases?.[p.id]?.status === "completed",
  ).length;
  const progressPct = Math.min(
    100,
    Math.round((completedCount / PHASES.length) * 100),
  );

  const barColor =
    status === "failed"
      ? "var(--color-error-text)"
      : status === "completed"
        ? "var(--color-success-500)"
        : undefined; // use gradient for running/pending

  const statusLabel = getStatusLabel(t);

  return (
    <div style={{
      width: "100%",
      maxWidth: 448,
      overflow: "hidden",
      borderRadius: 12,
      border: "1px solid var(--color-border)",
      backgroundColor: "var(--color-surface)",
      boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
    }}>
      {/* Header: run id + status */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        borderBottom: "1px solid var(--color-bg-muted)",
        padding: "10px 16px",
      }}>
        <div style={{ display: "flex", minWidth: 0, alignItems: "center", gap: 8 }}>
          <span style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--color-text-muted)",
          }}>
            {runId.slice(0, 8)}…
          </span>
          {isRunning && <LivePulse tone="primary" />}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--color-text-secondary)" }}>
            <Clock style={{ width: 12, height: 12 }} aria-hidden="true" />
            {formatElapsed(elapsed)}
          </span>
          <Badge variant={STATUS_VARIANT[status as keyof typeof STATUS_VARIANT] ?? "default"}>
            {statusLabel[status] ?? status}
          </Badge>
        </div>
      </div>

      {/* Phases */}
      <div style={{ padding: "12px 16px 0" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
          {PHASES.map((phase, i) => {
            const phaseData = phases?.[phase.id];
            const phaseStatus = phaseData?.status ?? "pending";
            const duration = phaseData?.duration_seconds;

            return (
              <div key={phase.id} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    borderRadius: 9999,
                    border: "1px solid",
                    padding: "4px 10px",
                    fontSize: 11.5,
                    fontWeight: 500,
                    transition: "color 150ms, background-color 150ms",
                    ...(PHASE_STATUS_STYLES[phaseStatus] ?? PHASE_STATUS_STYLES.pending),
                  }}
                  title={t(phase.descKey)}
                >
                  <PhaseIcon status={phaseStatus} />
                  <span>{t(phase.labelKey)}</span>
                  {typeof duration === "number" && (
                    <span style={{ opacity: 0.6 }}>
                      {duration.toFixed(0)}s
                    </span>
                  )}
                </div>
                {i < PHASES.length - 1 && (
                  <div style={{ width: 8, height: 1, backgroundColor: "var(--color-border)" }} aria-hidden="true" />
                )}
              </div>
            );
          })}
        </div>

        {/* Progress bar */}
        <div
          style={{
            marginTop: 12,
            height: 4,
            width: "100%",
            overflow: "hidden",
            borderRadius: 9999,
            backgroundColor: "var(--color-bg-muted)",
          }}
          role="progressbar"
          aria-valuenow={progressPct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className={barColor ? undefined : "progress-stripe"}
            style={{
              height: "100%",
              borderRadius: 9999,
              transition: "all 500ms",
              width: `${status === "completed" ? 100 : progressPct}%`,
              ...(barColor
                ? { backgroundColor: barColor }
                : {
                    background: "linear-gradient(to right, var(--color-primary-500, #06b6d4), #3b82f6)",
                  }),
            }}
          />
        </div>

        {/* Hint line */}
        <p style={{
          marginTop: 8,
          paddingBottom: 12,
          fontSize: 11.5,
          lineHeight: 1.625,
          color: "var(--color-text-secondary)",
        }}>
          {hint}
        </p>
      </div>
    </div>
  );
}
