import type { ReactNode, CSSProperties } from "react";

interface MetricTileProps {
  label: string;
  value: ReactNode;
  unit?: string;
  /** Tone for the value (e.g. success for positive counts). */
  tone?: "default" | "primary" | "success" | "warning" | "error";
  /** Optional icon at top-left. */
  icon?: ReactNode;
  className?: string;
}

const toneColors: Record<NonNullable<MetricTileProps["tone"]>, string> = {
  default: "var(--color-text)",
  primary: "var(--color-primary-700)",
  success: "var(--color-success-700)",
  warning: "var(--color-warning-text)",
  error: "var(--color-error-text)",
};

const containerStyle: CSSProperties = {
  borderRadius: 6,
  border: "1px solid var(--color-border)",
  backgroundColor: "var(--color-subtle-bg)",
  padding: "8px 12px",
};

const labelRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  fontSize: 10,
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "var(--color-text-secondary)",
};

const valueRowStyle: CSSProperties = {
  marginTop: 2,
  display: "flex",
  alignItems: "baseline",
  gap: 4,
};

const unitStyle: CSSProperties = {
  fontSize: 12,
  color: "var(--color-text-secondary)",
};

/**
 * Compact label / value tile used to surface a single quantitative fact.
 * Optimised for tabular display inside phase cards.
 */
export function MetricTile({
  label,
  value,
  unit,
  tone = "default",
  icon,
  className,
}: MetricTileProps) {
  const valueStyle: CSSProperties = {
    fontFamily: "var(--font-mono)",
    fontSize: 18,
    fontWeight: 600,
    fontVariantNumeric: "tabular-nums",
    color: toneColors[tone],
  };

  return (
    <div className={className} style={containerStyle}>
      <div style={labelRowStyle}>
        {icon}
        <span>{label}</span>
      </div>
      <div style={valueRowStyle}>
        <span style={valueStyle}>{value}</span>
        {unit && <span style={unitStyle}>{unit}</span>}
      </div>
    </div>
  );
}
