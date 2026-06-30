import type React from "react";

interface StatCardProps {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  value: string | number;
  label: string;
  accent?: string;
}

export function StatCard({ icon: Icon, value, label, accent }: StatCardProps) {
  const accentColor = accent ?? "#0891B2";
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 12,
      borderRadius: 8,
      border: "1px solid var(--color-bg-muted)",
      backgroundColor: "var(--color-subtle-bg)",
      padding: "12px 16px",
    }}>
      <div
        style={{
          display: "flex",
          width: 36,
          height: 36,
          flexShrink: 0,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 8,
          backgroundColor: `${accentColor}1a`,
        }}
      >
        <Icon style={{ width: 16, height: 16, color: accentColor }} />
      </div>
      <div>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 18,
            fontWeight: 600,
            lineHeight: 1.25,
            color: accentColor,
            margin: 0,
          }}
        >
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>
        <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0 }}>{label}</p>
      </div>
    </div>
  );
}
