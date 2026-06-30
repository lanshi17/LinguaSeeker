import type { CSSProperties } from "react";
import type { PhaseTimelineStep } from "../types/pipeline";

interface PhaseTimelineProps {
  steps: PhaseTimelineStep[];
}

const STATUS_STYLES: Record<string, CSSProperties> = {
  pending: { backgroundColor: "var(--color-border)", color: "var(--color-text-secondary)" },
  running: { backgroundColor: "var(--color-primary-100)", color: "var(--color-primary-700)", animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite" },
  completed: { backgroundColor: "var(--color-success-100)", color: "var(--color-success-700)" },
  failed: { backgroundColor: "var(--color-error-bg)", color: "var(--color-error-text)" },
  skipped: { backgroundColor: "var(--color-bg-muted)", color: "var(--color-text-muted)" },
};

const CONNECTOR_COLORS: Record<string, string> = {
  completed: "var(--color-success-400)",
  default: "var(--color-border)",
};

export function PhaseTimeline({ steps }: PhaseTimelineProps) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, overflowX: "auto", padding: "0 8px" }}>
      {steps.map((step, i) => {
        const nodeStyle = STATUS_STYLES[step.status] ?? STATUS_STYLES.pending;
        const connectorColor = step.status === "completed"
          ? CONNECTOR_COLORS.completed
          : CONNECTOR_COLORS.default;

        return (
          <div key={step.phaseId} style={{ display: "flex", alignItems: "center" }}>
            {/* Phase node */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div
                style={{
                  display: "flex",
                  width: 40,
                  height: 40,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: "50%",
                  fontSize: 14,
                  fontWeight: 600,
                  ...nodeStyle,
                }}
              >
                {i + 1}
              </div>
              <span style={{ marginTop: 8, fontSize: 12, fontWeight: 500, color: "var(--color-text-strong)" }}>
                {step.label}
              </span>
              {step.duration != null && (
                <span style={{ marginTop: 2, fontSize: 12, color: "var(--color-text-muted)" }}>
                  {step.duration.toFixed(1)}s
                </span>
              )}
            </div>

            {/* Connector line */}
            {i < steps.length - 1 && (
              <div
                style={{
                  margin: "0 8px",
                  height: 2,
                  width: 64,
                  backgroundColor: connectorColor,
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
