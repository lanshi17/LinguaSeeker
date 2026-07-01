import { STATUS_VARIANT } from "@/lib/constants/statusVariant";
export { STATUS_VARIANT };
import {
  FileText,
  BarChart3,
  Calendar,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { LiteratureEvidenceRow } from "../utils/literatureRows";
import { useI18n } from "@/lib/i18n";

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

export function literatureTitle(row: LiteratureEvidenceRow, t: (key: string) => string) {
  return row.title?.trim() || t("evidence.col.untitled");
}

const TONE_STYLES: Record<string, React.CSSProperties> = {
  primary: {
    borderColor: "var(--color-primary-200)",
    backgroundColor: "var(--color-highlight)",
    color: "var(--color-primary-800, #155e75)",
  },
  success: {
    borderColor: "var(--color-success-200)",
    backgroundColor: "var(--color-highlight-green)",
    color: "var(--color-success-800, #166534)",
  },
  amber: {
    borderColor: "var(--color-highlight-amber-border)",
    backgroundColor: "var(--color-highlight-amber)",
    color: "var(--color-warning-text)",
  },
  gray: {
    borderColor: "var(--color-border)",
    backgroundColor: "var(--color-bg)",
    color: "var(--color-text-strong)",
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
    return <span style={{ fontSize: 14, color: "var(--color-text-muted)" }}>{"\u2014"}</span>;
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
            maxWidth: "min(14rem, 100%)",
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
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            padding: "2px 8px",
            fontSize: 12,
            fontWeight: 500,
            color: "var(--color-text-secondary)",
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
          }}
        >
          +{hiddenCount}
        </span>
      )}
    </div>
  );
}

function IdentifierChip({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <span
      title={value ?? undefined}
      style={{
        display: "inline-flex",
        minWidth: 0,
        maxWidth: "100%",
        alignItems: "center",
        gap: 4,
        borderRadius: 4,
        backgroundColor: "var(--color-bg-muted)",
        padding: "2px 6px",
        fontSize: 12,
        color: "var(--color-text-secondary)",
      }}
    >
      <span style={{ flexShrink: 0, fontWeight: 600 }}>{label}</span>
      <span
        style={{
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontFamily: "var(--font-mono, monospace)",
        }}
      >
        {value ?? "\u2014"}
      </span>
    </span>
  );
}

export function LiteratureIdentifiers({ row }: { row: LiteratureEvidenceRow }) {
  const { t } = useI18n();
  return (
    <div
      style={{
        marginTop: 6,
        display: "flex",
        minWidth: 0,
        maxWidth: "100%",
        flexWrap: "wrap",
        gap: 6,
      }}
    >
      <IdentifierChip label={t("evidence.col.pmid")} value={row.pmid} />
      <IdentifierChip label="DOI" value={row.doi} />
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
        minWidth: 0,
        alignItems: "center",
        gap: 6,
        borderRadius: 6,
        backgroundColor: "var(--color-bg)",
        padding: "4px 8px",
        fontSize: 12,
      }}
    >
      <Icon style={{ width: 14, height: 14, color: "var(--color-text-muted)" }} />
      <span style={{ fontWeight: 500, color: "var(--color-text-strong)" }}>{value}</span>
      <span style={{ color: "var(--color-text-secondary)", whiteSpace: "nowrap" }}>{label}</span>
    </div>
  );
}

/** Renders the Literature column cell (desktop table + mobile card icon/title block). */
export function LiteratureCell({ row }: { row: LiteratureEvidenceRow }) {
  const { t } = useI18n();
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
          background: "linear-gradient(to bottom right, var(--color-primary-100), var(--color-primary-50))",
          color: "var(--color-primary-700, var(--color-primary-700))",
          boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
          transition: "transform 0.15s",
        }}
      >
        <FileText style={{ width: 18, height: 18 }} />
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <p
          className="edb-row-title edb-line-clamp-2"
          style={{ fontSize: 14, fontWeight: 600, lineHeight: "20px", color: "var(--color-text)", transition: "color 0.15s" }}
        >
          {literatureTitle(row, t)}
        </p>
        <LiteratureIdentifiers row={row} />
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
      style={{ color: "var(--color-text-strong)" }}
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
    <div style={{ display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap", fontSize: 12, color: "var(--color-text-secondary)" }}>
      <Calendar style={{ width: 14, height: 14, color: "var(--color-text-muted)" }} />
      {formatDate(row.createdAt)}
    </div>
  );
}

/** Renders the Review status column cell. */
export function ReviewCell({ row }: { row: LiteratureEvidenceRow }) {
  return (
    <>
      <Badge variant={STATUS_VARIANT[row.reviewStatus as keyof typeof STATUS_VARIANT] ?? "info"}>
        {row.reviewStatus}
      </Badge>
      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap", fontSize: 12, color: "var(--color-text-secondary)" }}>
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
        backgroundColor: "var(--color-bg-muted)",
        padding: "0 8px",
        fontSize: 14,
        fontWeight: 600,
        color: "var(--color-text-strong)",
      }}
    >
      {row.fieldCount}
    </span>
  );
}
