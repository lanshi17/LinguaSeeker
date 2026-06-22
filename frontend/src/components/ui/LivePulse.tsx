import type { CSSProperties } from "react";

type PulseTone = "primary" | "success" | "warning" | "error" | "neutral";

interface LivePulseProps {
  tone?: PulseTone;
  className?: string;
  label?: string;
}

const toneColors: Record<PulseTone, string> = {
  primary: "var(--color-primary-500, #06b6d4)",
  success: "var(--color-success-500, #22c55e)",
  warning: "#f59e0b",
  error: "#ef4444",
  neutral: "#9ca3af",
};

const dotStyle = (color: string): CSSProperties => ({
  position: "relative",
  display: "inline-flex",
  width: 10,
  height: 10,
  borderRadius: "50%",
  backgroundColor: color,
});

const ringStyle = (color: string): CSSProperties => ({
  position: "absolute",
  display: "inline-flex",
  width: "100%",
  height: "100%",
  borderRadius: "50%",
  backgroundColor: color,
  opacity: 0.4,
  animation: "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite",
});

export function LivePulse({ tone = "primary", className, label }: LivePulseProps) {
  const color = toneColors[tone];
  return (
    <span
      className={className}
      style={{ position: "relative", display: "inline-flex", width: 10, height: 10 }}
      role="status"
      aria-label={label ?? "In progress"}
    >
      <span style={ringStyle(color)} />
      <span style={dotStyle(color)} />
    </span>
  );
}
