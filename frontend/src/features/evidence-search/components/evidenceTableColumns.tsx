import {
  FileText,
  BarChart3,
  Calendar,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { LiteratureEvidenceRow } from "../utils/literatureRows";

export const STATUS_VARIANT: Record<
  string,
  "default" | "success" | "warning" | "error" | "info"
> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

export function formatPercent(value?: number | null) {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

export function formatDate(isoString?: string | null) {
  if (!isoString) {
    return "\u2014";
  }
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
      return "\u2014";
    }
    return date.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return "\u2014";
  }
}

export function joinedLabel(values: string[]) {
  return values.length > 0 ? values.join(", ") : "\u2014";
}

export function literatureTitle(row: LiteratureEvidenceRow) {
  return row.title?.trim() || "Untitled literature record";
}

const TONE_STYLES: Record<string, React.CSSProperties> = {
  primary: {
    borderColor: "rgba(165, 243, 252, 0.6)",
    backgroundColor: "rgba(236, 254, 255, 0.8)",
    color: "var(--color-primary-800, #155e75)",
  },
  success: {
    borderColor: "rgba(187, 247, 208, 0.6)",
    backgroundColor: "rgba(240, 253, 244, 0.8)",
    color: "var(--color-success-800, #166534)",
  },
  amber: {
    borderColor: "rgba(253, 230, 138, 0.6)",
    backgroundColor: "rgba(255, 251, 235, 0.8)",
    color: "#92400e",
  },
  gray: {
    borderColor: "#e5e7eb",
    backgroundColor: "#f9fafb",
    color: "#374151",
  },
};

export function TokenList({
  values,
  tone,
}: {
  values: string[];
  tone: "primary" | "success" | "amber" | "gray";
}) {
  const visible = values.slice(0, 3);
  const hiddenCount = Math.max(0, values.length - visible.length);
  const toneStyle = TONE_STYLES[tone];

  if (values.length === 0) {
    return <span style={{ fontSize: 14, color: "#9ca3af" }}>{"\u2014"}</span>;
  }

  return (
    <div
      style={{ display: "flex", minWidth: 0, flexWrap: "wrap", gap: 6 }}
      title={joinedLabel(values)}
    >
      {visible.map((value) => (
        <span
          key={value}
          style={{
            maxWidth: "12rem",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            borderRadius: 6,
            border: "1px solid",
            padding: "2px 8px",
            fontSize: 12,
            fontWeight: 500,
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            ...toneStyle,
          }}
        >
          {value}
        </span>
      ))}
      {hiddenCount > 0 && (
        <span
          style={{
            borderRadius: 6,
            border: "1px solid #e5e7eb",
            backgroundColor: "#fff",
            padding: "2px 8px",
            fontSize: 12,
            fontWeight: 500,
            color: "#6b7280",
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
          }}
        >
          +{hiddenCount}
        </span>
      )}
    </div>
  );
}

export function StatBadge({
  icon: Icon,
  value,
  label,
}: {
  icon: React.ComponentType<{ style?: React.CSSProperties }>;
  value: string | number;
  label: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 6,
        backgroundColor: "#f9fafb",
        padding: "4px 8px",
        fontSize: 12,
      }}
    >
      <Icon style={{ width: 14, height: 14, color: "#9ca3af" }} />
      <span style={{ fontWeight: 500, color: "#374151" }}>{value}</span>
      <span style={{ color: "#6b7280" }}>{label}</span>
    </div>
  );
}

/** Renders the Literature column cell (desktop table + mobile card icon/title block). */
export function LiteratureCell({ row }: { row: LiteratureEvidenceRow }) {
  return (
    <div style={{ display: "flex", minWidth: 0, alignItems: "flex-start", gap: 12 }}>
      <span
        className="edb-row-icon"
        style={{
          display: "flex",
          height: 40,
          width: 40,
          flexShrink: 0,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 8,
          background: "linear-gradient(to bottom right, var(--color-primary-100, #cffafe), var(--color-primary-50, #ecfeff))",
          color: "var(--color-primary-700, #0e7490)",
          boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
          transition: "transform 0.15s",
        }}
      >
        <FileText style={{ width: 18, height: 18 }} />
      </span>
      <div style={{ minWidth: 0 }}>
        <p
          className="edb-row-title edb-line-clamp-2"
          style={{ fontSize: 14, fontWeight: 600, lineHeight: "20px", color: "#030712", transition: "color 0.15s" }}
        >
          {literatureTitle(row)}
        </p>
        <p
          style={{
            marginTop: 4,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            fontFamily: "monospace",
            fontSize: 12,
            color: "#9ca3af",
          }}
        >
          {row.documentId.slice(0, 8)}...
        </p>
        <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#6b7280" }}>
          <span style={{ borderRadius: 4, backgroundColor: "#f3f4f6", padding: "2px 6px", fontWeight: 500 }}>
            PMID {row.pmid ?? "\u2014"}
          </span>
        </div>
      </div>
    </div>
  );
}

/** Renders the Evidence Focus column cell. */
export function EvidenceFocusCell({ row }: { row: LiteratureEvidenceRow }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <TokenList values={row.genes} tone="primary" />
      <TokenList values={row.variants} tone="success" />
    </div>
  );
}

/** Renders the Disease column cell. */
export function DiseaseCell({ row }: { row: LiteratureEvidenceRow }) {
  return (
    <p
      className="edb-line-clamp-3"
      style={{ color: "#374151" }}
      title={joinedLabel(row.diseases)}
    >
      {joinedLabel(row.diseases)}
    </p>
  );
}

/** Renders the Classification column cell. */
export function ClassificationCell({ row }: { row: LiteratureEvidenceRow }) {
  return <TokenList values={row.classifications} tone="amber" />;
}

/** Renders the Created date column cell. */
export function CreatedCell({ row }: { row: LiteratureEvidenceRow }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#6b7280" }}>
      <Calendar style={{ width: 14, height: 14, color: "#9ca3af" }} />
      {formatDate(row.createdAt)}
    </div>
  );
}

/** Renders the Review status column cell. */
export function ReviewCell({ row }: { row: LiteratureEvidenceRow }) {
  return (
    <>
      <Badge variant={STATUS_VARIANT[row.reviewStatus] ?? "info"}>
        {row.reviewStatus}
      </Badge>
      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "#6b7280" }}>
        <BarChart3 style={{ width: 12, height: 12 }} />
        {formatPercent(row.avgConfidence)}
      </div>
    </>
  );
}

/** Renders the Fields count column cell. */
export function FieldsCell({ row }: { row: LiteratureEvidenceRow }) {
  return (
    <span
      style={{
        display: "inline-flex",
        height: 28,
        minWidth: "1.75rem",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 6,
        backgroundColor: "#f3f4f6",
        padding: "0 8px",
        fontSize: 14,
        fontWeight: 600,
        color: "#374151",
      }}
    >
      {row.fieldCount}
    </span>
  );
}
