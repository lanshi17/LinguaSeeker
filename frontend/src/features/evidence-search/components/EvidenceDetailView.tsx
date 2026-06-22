import { useMemo, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  BookOpen,
  Columns2,
  FileText,
  Highlighter,
  Languages,
  ListChecks,
  Percent,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Database,
  Hash,
  Link2,
  TrendingUp,
  AlertCircle,
  Dna,
  FlaskConical,
  Stethoscope,
  Layers3,
  Pencil,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/Badge";
import { useEvidenceGroupDetail } from "../hooks/useEvidenceGroupDetail";
import { EvidenceDetailSkeleton } from "./EvidenceDetailSkeleton";
import { EvidenceCorrectionForm } from "./EvidenceCorrectionForm";
import { EvidenceAuditHistory } from "./EvidenceAuditHistory";
import type {
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
  EvidenceHighlightTone,
} from "../types/evidenceSearch";
import {
  buildEvidenceDocument,
  CATEGORY_COLORS,
  EVIDENCE_CATEGORIES,
  countEvidenceCategories,
  hasTranslatedDocumentText,
  type EvidenceDocumentHighlight,
  type EvidenceDocumentParagraph,
} from "../utils/evidenceDocument";
import { categoryLabel } from "../utils/categoryStyles";
import {
  buildBilingualCompareHref,
  findInitialEvidenceId,
} from "../utils/literatureRows";
import { MarkdownDocumentViewer } from "./MarkdownDocumentViewer";

type DetailViewMode = "overview" | "compare";

interface EvidenceDetailViewProps {
  groupId: string;
  initialEvidenceId?: string;
  initialView?: DetailViewMode;
}

const STATUS_VARIANT: Record<
  string,
  "default" | "success" | "warning" | "error" | "info"
> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

const HIGHLIGHT_TONES: EvidenceHighlightTone[] = [
  "gene",
  "variant",
  "disease",
  "classification",
  "functional",
  "neutral",
];

/* ---- Inline style helpers derived from CATEGORY_COLORS hex ---- */

function chipInlineStyle(hex?: string): React.CSSProperties {
  if (!hex) return { borderColor: "#e5e7eb", backgroundColor: "#f9fafb", color: "#374151" };
  return { borderColor: hex + "60", backgroundColor: hex + "15", color: hex };
}

function markInlineStyle(hex?: string, selected?: boolean): React.CSSProperties {
  const base: React.CSSProperties = hex
    ? { backgroundColor: hex + "40", color: hex, boxShadow: `0 0 0 1px ${hex}50` }
    : { backgroundColor: "#e5e7eb", color: "#030712", boxShadow: "0 0 0 1px #d1d5db" };
  if (selected) {
    base.outline = "2px solid var(--color-primary-700, #0e7490)";
    base.outlineOffset = "2px";
  }
  return base;
}

/* ---- Utility functions ---- */

function formatPercent(value?: number | null) {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function categoryFromItem(item?: EvidenceGroupItem | null) {
  if (!item) {
    return null;
  }
  if (item.category) {
    return item.category;
  }
  return item.field_id.includes(".") ? item.field_id.split(".", 1)[0] : null;
}

function itemLabel(item: EvidenceGroupItem) {
  return item.field_name ?? item.field_id;
}

function countEntries(record: Record<string, number>) {
  return Object.entries(record).sort(([a], [b]) => a.localeCompare(b));
}

function selectedTraceFor(
  detail: EvidenceGroupDetailResponse,
  selectedEvidenceId: string | null,
) {
  if (!selectedEvidenceId) {
    return detail.traces[0] ?? null;
  }

  const selectedItem = detail.items.find(
    (item) => item.canonical_evidence_id === selectedEvidenceId,
  );
  return (
    detail.traces.find(
      (trace) => trace.canonical_evidence_id === selectedEvidenceId,
    ) ??
    detail.traces.find((trace) => trace.field_id === selectedItem?.field_id) ??
    detail.traces[0] ??
    null
  );
}

function detailTitle(detail: EvidenceGroupDetailResponse) {
  const title = detail.title?.trim();
  return title || "Untitled literature record";
}

/* ---- Sub-components ---- */

function StatBadge({
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

function MetadataToken({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value?: string | null;
  icon?: React.ComponentType<{ style?: React.CSSProperties }>;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        maxWidth: "100%",
        alignItems: "center",
        gap: 6,
        borderRadius: 6,
        border: "1px solid rgba(165, 243, 252, 0.6)",
        backgroundColor: "#fff",
        padding: "4px 10px",
        fontSize: 12,
        color: "var(--color-primary-900, #164e63)",
        boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
      }}
    >
      {Icon && <Icon style={{ width: 12, height: 12, flexShrink: 0, color: "var(--color-primary-500, #06b6d4)" }} />}
      <span style={{ fontWeight: 600 }}>{label}</span>
      <span
        style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontFamily: "monospace",
        }}
      >
        {value?.trim() || "\u2014"}
      </span>
    </span>
  );
}

function EvidenceTonePill({ item }: { item: EvidenceGroupItem }) {
  const cat = categoryFromItem(item);
  const hex = cat && CATEGORY_COLORS[cat] ? CATEGORY_COLORS[cat].hex : undefined;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 6,
        border: "1px solid",
        padding: "4px 8px",
        fontSize: 12,
        fontWeight: 500,
        ...chipInlineStyle(hex),
      }}
    >
      {cat && CATEGORY_COLORS[cat] && (
        <span
          style={{
            display: "inline-block",
            width: 8,
            height: 8,
            flexShrink: 0,
            borderRadius: "50%",
            backgroundColor: CATEGORY_COLORS[cat].hex,
          }}
          aria-hidden="true"
        />
      )}
      {categoryLabel(cat)}
    </span>
  );
}

const FIELD_ID_TO_CARD_FIELD: Record<string, string> = {
  "A.gene_symbol": "gene",
  "B.disease_diagnosis": "disease",
  "B.clinical_diagnosis": "disease",
  "J.authority_classification": "classification",
};

function cardFieldForFieldId(fieldId: string): string | null {
  if (FIELD_ID_TO_CARD_FIELD[fieldId]) return FIELD_ID_TO_CARD_FIELD[fieldId];
  if (fieldId.startsWith("A.variant_hgvs_")) return "variant";
  return null;
}

function EvidenceItemSummary({
  groupId,
  item,
}: {
  groupId: string;
  item: EvidenceGroupItem;
}) {
  const [editing, setEditing] = useState(false);
  const cardField = cardFieldForFieldId(item.field_id);

  return (
    <article className="edb-evidence-card">
      <div
        className="edb-evidence-card-accent"
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          height: "100%",
          width: 4,
          background: "linear-gradient(to bottom, var(--color-primary-400, #22d3ee), var(--color-primary-600, #0891b2))",
          opacity: 0,
          transition: "opacity 0.15s",
        }}
      />

      <div style={{ padding: 20 }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
              <EvidenceTonePill item={item} />
              <Badge variant={STATUS_VARIANT[item.review_status] ?? "default"}>
                {item.review_status}
              </Badge>
            </div>
            <h3 style={{ marginTop: 12, fontSize: 14, fontWeight: 600, color: "#111827" }}>
              {itemLabel(item)}
            </h3>
            <p style={{ marginTop: 4, fontFamily: "monospace", fontSize: 12, color: "#6b7280" }}>
              {item.field_id}
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              type="button"
              onClick={() => setEditing((v) => !v)}
              style={{
                display: "inline-flex",
                height: 36,
                cursor: "pointer",
                alignItems: "center",
                gap: 6,
                borderRadius: 6,
                border: "1px solid",
                padding: "0 10px",
                fontSize: 14,
                fontWeight: 500,
                transition: "color 0.15s, border-color 0.15s, background-color 0.15s",
                ...(editing
                  ? {
                      borderColor: "var(--color-primary-300, #67e8f9)",
                      backgroundColor: "var(--color-primary-100, #cffafe)",
                      color: "var(--color-primary-800, #155e75)",
                    }
                  : {
                      borderColor: "#e5e7eb",
                      backgroundColor: "#fff",
                      color: "#4b5563",
                    }),
              }}
            >
              <Pencil style={{ width: 14, height: 14 }} />
              {editing ? "Close" : "Edit"}
            </button>
            <Link
              to={buildBilingualCompareHref(groupId, item.canonical_evidence_id)}
              className="edb-focusable-link"
              style={{
                display: "inline-flex",
                height: 36,
                cursor: "pointer",
                alignItems: "center",
                gap: 8,
                borderRadius: 6,
                border: "1px solid var(--color-primary-200, #a5f3fc)",
                backgroundColor: "var(--color-primary-50, #ecfeff)",
                padding: "0 12px",
                fontSize: 14,
                fontWeight: 500,
                color: "var(--color-primary-800, #155e75)",
                textDecoration: "none",
                transition: "background-color 0.15s",
              }}
            >
              <Columns2 style={{ width: 16, height: 16 }} />
              Compare
            </Link>
          </div>
        </div>

        <p className="edb-line-clamp-3" style={{ marginTop: 16, fontSize: 14, lineHeight: "24px", color: "#374151" }}>
          {item.value ?? "\u2014"}
        </p>

        <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 8, borderTop: "1px solid #f3f4f6", paddingTop: 12 }}>
          <StatBadge icon={Percent} value={formatPercent(item.confidence)} label="confidence" />
          <StatBadge icon={Layers3} value={item.track ?? "\u2014"} label="track" />
          <StatBadge icon={FileText} value={item.page ?? "\u2014"} label="page" />
        </div>
      </div>

      {editing && (
        <EvidenceCorrectionForm
          canonicalEvidenceId={item.canonical_evidence_id}
          currentValue={item.value ?? null}
          currentStatus={item.review_status}
          fieldId={item.field_id}
          cardField={cardField}
          groupId={groupId}
          onClose={() => setEditing(false)}
        />
      )}
    </article>
  );
}

function LiteratureOverview({
  detail,
  groupId,
}: {
  detail: EvidenceGroupDetailResponse;
  groupId: string;
}) {
  return (
    <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Link
        to="/evidence"
        className="edb-back-link"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          fontSize: 14,
          fontWeight: 500,
          color: "#6b7280",
          textDecoration: "none",
          transition: "color 0.15s",
        }}
      >
        <ArrowLeft style={{ width: 16, height: 16 }} />
        Back to literature
      </Link>

      <section style={{ overflow: "hidden", borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
        <div
          style={{
            position: "relative",
            borderBottom: "1px solid var(--color-primary-100, #cffafe)",
            background: "linear-gradient(to right, var(--color-primary-50, #ecfeff), rgba(236,254,255,0.5), transparent)",
            padding: "20px 24px",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              height: "100%",
              width: 4,
              background: "linear-gradient(to bottom, var(--color-primary-400, #22d3ee), var(--color-primary-600, #0891b2))",
            }}
          />
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
            <div style={{ minWidth: 0 }}>
              <p
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "var(--color-primary-800, #155e75)",
                  margin: 0,
                }}
              >
                <BookOpen style={{ width: 16, height: 16 }} />
                Literature record
              </p>
              <h2 style={{ marginTop: 8, maxWidth: 896, fontSize: 20, fontWeight: 600, lineHeight: "28px", color: "#030712" }}>
                {detailTitle(detail)}
              </h2>
              <div style={{ marginTop: 12, display: "flex", maxWidth: 896, flexWrap: "wrap", gap: 8 }}>
                <MetadataToken label="UUID" value={detail.source_document_id} icon={Hash} />
                <MetadataToken label="PMID" value={detail.pmid} icon={FileText} />
                <MetadataToken label="DOI" value={detail.doi} icon={Link2} />
              </div>
            </div>
            <Badge variant={STATUS_VARIANT.approved}>Traceable</Badge>
          </div>
        </div>

        <div className="edb-overview-meta-grid">
          {(
            [
              { label: "Gene", value: detail.gene, Icon: Dna },
              { label: "Variant", value: detail.variant, Icon: FlaskConical },
              { label: "Disease", value: detail.disease, Icon: Stethoscope },
              { label: "Classification", value: detail.classification, Icon: ShieldCheck },
            ] as const
          ).map(({ label, value, Icon }) => (
            <div key={label} className="edb-overview-meta-cell">
              <p
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "#9ca3af",
                  margin: 0,
                }}
              >
                <Icon style={{ width: 14, height: 14 }} />
                {label}
              </p>
              <p className="edb-line-clamp-3" style={{ marginTop: 8, fontSize: 14, fontWeight: 500, color: "#111827" }}>
                {value ?? "\u2014"}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="edb-overview-layout">
        <aside style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <section style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
            <div style={{ borderBottom: "1px solid #f3f4f6", padding: "12px 20px" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
                <ListChecks style={{ width: 16, height: 16, color: "var(--color-primary-700, #0e7490)" }} />
                Evidence coverage
              </h3>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
              {[
                { label: "Items", value: detail.item_count, icon: Database },
                { label: "Confidence", value: formatPercent(detail.avg_confidence), icon: TrendingUp },
                { label: "Traces", value: detail.traces.length, icon: Search },
                { label: "Fields", value: Object.keys(detail.distribution.by_field).length, icon: FileText },
              ].map((stat) => (
                <div key={stat.label} className="edb-coverage-stat-cell">
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <stat.icon style={{ width: 14, height: 14, color: "#9ca3af" }} />
                    <p style={{ fontSize: 12, fontWeight: 500, color: "#6b7280", margin: 0 }}>{stat.label}</p>
                  </div>
                  <p style={{ marginTop: 6, fontSize: 20, fontWeight: 700, color: "#030712" }}>
                    {stat.value}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
            <div style={{ borderBottom: "1px solid #f3f4f6", padding: "12px 20px" }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
                Evidence categories
              </h3>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: 16 }}>
              {countEntries(detail.distribution.by_category).map(([key, count]) => (
                <span
                  key={key}
                  style={{
                    borderRadius: 6,
                    border: "1px solid #e5e7eb",
                    backgroundColor: "#f9fafb",
                    padding: "6px 10px",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#374151",
                    boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
                  }}
                >
                  {categoryLabel(key)} · {count}
                </span>
              ))}
            </div>
          </section>

          <section style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
            <div style={{ borderBottom: "1px solid #f3f4f6", padding: "12px 20px" }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
                Review status
              </h3>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: 16 }}>
              {countEntries(detail.distribution.by_status).map(([key, count]) => (
                <Badge key={key} variant={STATUS_VARIANT[key] ?? "default"}>
                  {key}: {count}
                </Badge>
              ))}
            </div>
          </section>

          <EvidenceAuditHistory sourceDocumentId={detail.source_document_id} />
        </aside>

        <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              borderRadius: 12,
              border: "1px solid #e5e7eb",
              backgroundColor: "#fff",
              padding: "16px 20px",
              boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  display: "flex",
                  height: 40,
                  width: 40,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 8,
                  backgroundColor: "var(--color-primary-50, #ecfeff)",
                }}
              >
                <ListChecks style={{ width: 20, height: 20, color: "var(--color-primary-600, #0891b2)" }} />
              </div>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 600, color: "#030712", margin: 0 }}>
                  Extracted evidence fields
                </h2>
                <p style={{ marginTop: 2, fontSize: 14, color: "#6b7280" }}>
                  {detail.items.length} field-level evidence items
                </p>
              </div>
            </div>
            {detail.items[0] && (
              <Link
                to={buildBilingualCompareHref(groupId, detail.items[0].canonical_evidence_id)}
                className="edb-focusable-link"
                style={{
                  display: "inline-flex",
                  height: 40,
                  cursor: "pointer",
                  alignItems: "center",
                  gap: 8,
                  borderRadius: 6,
                  backgroundColor: "var(--color-primary-700, #0e7490)",
                  padding: "0 12px",
                  fontSize: 14,
                  fontWeight: 500,
                  color: "#fff",
                  textDecoration: "none",
                  transition: "background-color 0.15s",
                }}
              >
                <Languages style={{ width: 16, height: 16 }} />
                Full-text comparison
              </Link>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {detail.items.map((item) => (
              <EvidenceItemSummary
                key={item.canonical_evidence_id}
                groupId={groupId}
                item={item}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function normalizedHighlights(paragraph: EvidenceDocumentParagraph) {
  const highlights = [...paragraph.highlights].sort((a, b) => a.start - b.start);
  const normalized: EvidenceDocumentHighlight[] = [];
  let cursor = 0;

  for (const highlight of highlights) {
    const start = Math.max(cursor, Math.max(0, Math.min(highlight.start, paragraph.text.length)));
    const end = Math.max(start, Math.min(highlight.end, paragraph.text.length));
    if (end <= start) {
      continue;
    }
    normalized.push({ ...highlight, start, end });
    cursor = end;
  }

  return normalized;
}

function HighlightedParagraph({
  paragraph,
}: {
  paragraph: EvidenceDocumentParagraph;
}) {
  const highlights = normalizedHighlights(paragraph);
  const nodes: ReactNode[] = [];
  let cursor = 0;

  highlights.forEach((highlight, index) => {
    if (highlight.start > cursor) {
      nodes.push(paragraph.text.slice(cursor, highlight.start));
    }
    const hex = highlight.category && CATEGORY_COLORS[highlight.category]
      ? CATEGORY_COLORS[highlight.category].hex
      : undefined;
    nodes.push(
      <mark
        key={`${highlight.evidenceId}-${highlight.start}-${index}`}
        style={{
          borderRadius: 4,
          padding: "2px 4px",
          fontWeight: 600,
          ...markInlineStyle(hex, highlight.selected),
        }}
        aria-label={`${categoryLabel(highlight.category)} evidence: ${highlight.label}`}
      >
        {paragraph.text.slice(highlight.start, highlight.end)}
      </mark>,
    );
    cursor = highlight.end;
  });

  if (cursor < paragraph.text.length) {
    nodes.push(paragraph.text.slice(cursor));
  }

  return (
    <div style={{ borderBottom: "1px solid #f3f4f6", padding: "16px 0" }}>
      <div style={{ marginBottom: 8, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontSize: 12, color: "#6b7280" }}>
        <span
          style={{
            borderRadius: 6,
            backgroundColor: "#f3f4f6",
            padding: "4px 8px",
            fontWeight: 500,
            color: "#374151",
          }}
        >
          {paragraph.highlights[0]?.label ?? "Document text"}
        </span>
        <span>Page {paragraph.page ?? "\u2014"}</span>
      </div>
      <p style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: "28px", color: "#1f2937" }}>
        {nodes.length > 0 ? nodes : paragraph.text}
      </p>
    </div>
  );
}

function EvidenceDocumentReader({
  title,
  paragraphs,
}: {
  title: string;
  paragraphs: EvidenceDocumentParagraph[];
}) {
  const isFullText = paragraphs.length === 1 && paragraphs[0].text.length > 500;

  return (
    <section style={{ overflow: "hidden", borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
      <div
        style={{
          position: "sticky",
          top: 0,
          zIndex: 10,
          borderBottom: "1px solid #f3f4f6",
          background: "linear-gradient(to right, #f9fafb, #f9fafb, rgba(249,250,251,0.5))",
          padding: "12px 20px",
          backdropFilter: "blur(4px)",
        }}
      >
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "#030712", margin: 0 }}>{title}</h3>
        <p style={{ marginTop: 2, fontSize: 12, color: "#6b7280" }}>
          {isFullText
            ? "Full document with evidence highlights"
            : `${paragraphs.length} aligned paragraph${paragraphs.length !== 1 ? "s" : ""}`}
        </p>
      </div>
      <div style={{ maxHeight: 720, overflowY: "auto", padding: "0 20px" }}>
        {paragraphs.length > 0 ? (
          isFullText ? (
            <MarkdownDocumentViewer
              markdown={paragraphs[0].text}
              highlights={paragraphs[0].highlights}
            />
          ) : (
            paragraphs.map((paragraph) => (
              <HighlightedParagraph key={paragraph.id} paragraph={paragraph} />
            ))
          )
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "48px 8px", textAlign: "center" }}>
            <div
              style={{
                display: "flex",
                height: 48,
                width: 48,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 12,
                backgroundColor: "#f3f4f6",
              }}
            >
              <FileText style={{ width: 24, height: 24, color: "#9ca3af" }} />
            </div>
            <p style={{ fontSize: 14, color: "#6b7280" }}>
              No document text is available for this track.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function CategoryLayerToggle({
  checked,
  count,
  onChange,
  category,
}: {
  checked: boolean;
  count: number;
  onChange: () => void;
  category: string;
}) {
  const cat = CATEGORY_COLORS[category];
  const baseStyle: React.CSSProperties = {
    display: "flex",
    minHeight: 44,
    cursor: count === 0 ? "not-allowed" : "pointer",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    borderRadius: 8,
    border: "1px solid",
    padding: "8px 12px",
    transition: "color 0.15s, border-color 0.15s, background-color 0.15s",
    opacity: count === 0 ? 0.5 : 1,
  };

  if (checked && cat) {
    baseStyle.borderColor = cat.hex + "40";
    baseStyle.backgroundColor = cat.hex + "10";
  } else if (checked) {
    baseStyle.borderColor = "var(--color-primary-200, #a5f3fc)";
    baseStyle.backgroundColor = "var(--color-primary-50, #ecfeff)";
  } else {
    baseStyle.borderColor = "#e5e7eb";
    baseStyle.backgroundColor = "#fff";
  }

  return (
    <label className="edb-toggle-label" style={baseStyle}>
      <input
        type="checkbox"
        checked={checked}
        disabled={count === 0}
        onChange={onChange}
        className="edb-toggle-input"
        style={{ position: "absolute", width: 1, height: 1, padding: 0, margin: -1, overflow: "hidden", clip: "rect(0,0,0,0)", whiteSpace: "nowrap", borderWidth: 0 }}
      />
      <span style={{ display: "flex", minWidth: 0, alignItems: "center", gap: 8 }}>
        <span
          style={{
            display: "inline-block",
            width: 12,
            height: 12,
            flexShrink: 0,
            borderRadius: "50%",
            backgroundColor: cat?.hex ?? "#9CA3AF",
          }}
          aria-hidden="true"
        />
        <span style={{ minWidth: 0 }}>
          <span
            style={{
              display: "block",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontSize: 14,
              fontWeight: 500,
              color: "#111827",
            }}
          >
            {cat?.label ?? category}
          </span>
          <span style={{ fontSize: 12, color: "#6b7280" }}>
            {count} item{count !== 1 ? "s" : ""}
          </span>
        </span>
      </span>
      <span
        className="edb-toggle-track"
        style={{
          position: "relative",
          height: 24,
          width: 44,
          flexShrink: 0,
          borderRadius: 9999,
          transition: "background-color 0.15s",
          backgroundColor: checked ? "var(--color-primary-700, #0e7490)" : "#d1d5db",
        }}
        aria-hidden="true"
      >
        <span
          style={{
            position: "absolute",
            left: 4,
            top: 4,
            height: 16,
            width: 16,
            borderRadius: "50%",
            backgroundColor: "#fff",
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            transition: "transform 0.15s",
            transform: checked ? "translateX(20px)" : "translateX(0)",
          }}
        />
      </span>
    </label>
  );
}

function BilingualCompareView({
  detail,
  groupId,
  selectedEvidenceId,
  setSelectedEvidenceId,
}: {
  detail: EvidenceGroupDetailResponse;
  groupId: string;
  selectedEvidenceId: string | null;
  setSelectedEvidenceId: (value: string) => void;
}) {
  const [enabledTones] = useState<Set<EvidenceHighlightTone>>(
    () => new Set(HIGHLIGHT_TONES),
  );
  const [enabledCategories, setEnabledCategories] = useState<Set<string>>(
    () => new Set(EVIDENCE_CATEGORIES),
  );
  const selectedItem =
    detail.items.find(
      (item) => item.canonical_evidence_id === selectedEvidenceId,
    ) ??
    detail.items[0] ??
    null;
  const selectedTrace = selectedTraceFor(detail, selectedEvidenceId);
  const categoryCounts = useMemo(
    () => countEvidenceCategories(detail.items),
    [detail.items],
  );
  const originalDocument = useMemo(
    () =>
      buildEvidenceDocument(
        detail,
        "original",
        enabledTones,
        selectedEvidenceId,
        enabledCategories,
      ),
    [detail, enabledTones, selectedEvidenceId, enabledCategories],
  );
  const translatedDocument = useMemo(
    () =>
      buildEvidenceDocument(
        detail,
        "translated",
        enabledTones,
        selectedEvidenceId,
        enabledCategories,
      ),
    [detail, enabledTones, selectedEvidenceId, enabledCategories],
  );
  const showTranslatedDocument = hasTranslatedDocumentText(detail);

  const toggleCategory = (cat: string) => {
    setEnabledCategories((current) => {
      const next = new Set(current);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  };

  return (
    <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Link
        to={`/evidence/detail?groupId=${encodeURIComponent(groupId)}`}
        className="edb-back-link"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          fontSize: 14,
          fontWeight: 500,
          color: "#6b7280",
          textDecoration: "none",
          transition: "color 0.15s",
        }}
      >
        <ArrowLeft style={{ width: 16, height: 16 }} />
        Back to literature detail
      </Link>

      <section style={{ overflow: "hidden", borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
        <div
          style={{
            position: "relative",
            borderBottom: "1px solid #f3e8ff",
            background: "linear-gradient(to right, #faf5ff, rgba(250,245,255,0.5), transparent)",
            padding: "20px 24px",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              height: "100%",
              width: 4,
              background: "linear-gradient(to bottom, #c084fc, #9333ea)",
            }}
          />
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
            <div style={{ minWidth: 0 }}>
              <p
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "#6b21a8",
                  margin: 0,
                }}
              >
                <Columns2 style={{ width: 16, height: 16 }} />
                Bilingual full-text document
              </p>
              <h2 style={{ marginTop: 8, maxWidth: 896, fontSize: 20, fontWeight: 600, lineHeight: "28px", color: "#030712" }}>
                {detailTitle(detail)}
              </h2>
              <div style={{ marginTop: 12, display: "flex", maxWidth: 896, flexWrap: "wrap", gap: 8 }}>
                <MetadataToken label="UUID" value={detail.source_document_id} icon={Hash} />
                <MetadataToken label="PMID" value={detail.pmid} icon={FileText} />
                <MetadataToken label="DOI" value={detail.doi} icon={Link2} />
              </div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
              {selectedItem && <EvidenceTonePill item={selectedItem} />}
              {selectedItem && (
                <Badge variant={STATUS_VARIANT[selectedItem.review_status] ?? "default"}>
                  {selectedItem.review_status}
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="edb-compare-stats-grid">
          {[
            { label: "Item confidence", value: formatPercent(selectedItem?.confidence), icon: TrendingUp },
            { label: "Alignment confidence", value: formatPercent(selectedTrace?.alignment_confidence), icon: ShieldCheck },
            { label: "Source page", value: selectedTrace?.original?.page ?? selectedTrace?.translated?.page ?? selectedItem?.page ?? "\u2014", icon: FileText },
          ].map((stat) => (
            <div key={stat.label} className="edb-compare-stat-cell">
              <div
                style={{
                  display: "flex",
                  height: 36,
                  width: 36,
                  flexShrink: 0,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 8,
                  background: "linear-gradient(to bottom right, #f3e8ff, #faf5ff)",
                }}
              >
                <stat.icon style={{ width: 16, height: 16, color: "#7e22ce" }} />
              </div>
              <div>
                <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>{stat.label}</p>
                <p style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
                  {stat.value}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="edb-compare-layout">
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <section style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
            <div style={{ borderBottom: "1px solid #f3f4f6", padding: "12px 16px" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
                <SlidersHorizontal style={{ width: 16, height: 16, color: "var(--color-primary-700, #0e7490)" }} />
                Evidence categories
              </h3>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 16 }}>
              {EVIDENCE_CATEGORIES.map((cat) => (
                <CategoryLayerToggle
                  key={cat}
                  category={cat}
                  count={categoryCounts[cat] ?? 0}
                  checked={enabledCategories.has(cat)}
                  onChange={() => toggleCategory(cat)}
                />
              ))}
            </div>
          </section>

          <section style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
            <div style={{ borderBottom: "1px solid #f3f4f6", padding: "12px 16px" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
                <Search style={{ width: 16, height: 16, color: "var(--color-primary-700, #0e7490)" }} />
                Evidence navigator
              </h3>
            </div>
            <div style={{ maxHeight: 460, overflowY: "auto", padding: "16px 12px 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
              {detail.items.map((item) => {
                const active =
                  item.canonical_evidence_id === selectedItem?.canonical_evidence_id;
                const cat = categoryFromItem(item);
                const catColor = cat && CATEGORY_COLORS[cat];
                const navItemStyle: React.CSSProperties = {
                  width: "100%",
                  cursor: "pointer",
                  borderRadius: 8,
                  border: "1px solid",
                  padding: 12,
                  textAlign: "left",
                  transition: "all 0.15s",
                  background: "none",
                };
                if (active && catColor) {
                  navItemStyle.borderColor = catColor.hex + "60";
                  navItemStyle.backgroundColor = catColor.hex + "12";
                  navItemStyle.boxShadow = "0 1px 2px 0 rgba(0,0,0,0.05)";
                } else if (active) {
                  navItemStyle.borderColor = "var(--color-primary-300, #67e8f9)";
                  navItemStyle.backgroundColor = "var(--color-primary-50, #ecfeff)";
                  navItemStyle.boxShadow = "0 1px 2px 0 rgba(0,0,0,0.05)";
                } else {
                  navItemStyle.borderColor = "#e5e7eb";
                  navItemStyle.backgroundColor = "#fff";
                }
                return (
                  <button
                    key={item.canonical_evidence_id}
                    type="button"
                    onClick={() => setSelectedEvidenceId(item.canonical_evidence_id)}
                    className="edb-nav-item edb-focusable-btn"
                    style={navItemStyle}
                  >
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
                      <EvidenceTonePill item={item} />
                      <span style={{ fontSize: 12, color: "#6b7280" }}>
                        {formatPercent(item.confidence)}
                      </span>
                    </div>
                    <p className="edb-nav-item-title edb-line-clamp-2" style={{ marginTop: 8, fontSize: 14, fontWeight: 500, color: "#111827", transition: "color 0.15s" }}>
                      {itemLabel(item)}
                    </p>
                    <p className="edb-line-clamp-2" style={{ marginTop: 4, fontSize: 12, color: "#6b7280" }}>
                      {item.value ?? "\u2014"}
                    </p>
                  </button>
                );
              })}
            </div>
          </section>
        </aside>

        <section style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ overflow: "hidden", borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
            <div
              style={{
                position: "relative",
                borderBottom: "1px solid #f3f4f6",
                background: "linear-gradient(to right, rgba(236,254,255,0.5), transparent)",
                padding: "16px 20px",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  height: "100%",
                  width: 4,
                  background: "linear-gradient(to bottom, var(--color-primary-400, #22d3ee), var(--color-primary-600, #0891b2))",
                }}
              />
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                <div>
                  <p
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 12,
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      color: "var(--color-primary-800, #155e75)",
                      margin: 0,
                    }}
                  >
                    <Highlighter style={{ width: 16, height: 16 }} />
                    Active evidence
                  </p>
                  <h3 style={{ marginTop: 8, fontSize: 14, fontWeight: 600, color: "#030712" }}>
                    {selectedItem ? itemLabel(selectedItem) : "No evidence selected"}
                  </h3>
                  <p style={{ marginTop: 4, fontFamily: "monospace", fontSize: 12, color: "#6b7280" }}>
                    {selectedItem?.field_id ?? "\u2014"}
                  </p>
                </div>
                {selectedItem && (
                  <Badge variant={STATUS_VARIANT[selectedItem.review_status] ?? "default"}>
                    {selectedItem.review_status}
                  </Badge>
                )}
              </div>
            </div>
            <div style={{ padding: "16px 20px" }}>
              <p style={{ fontSize: 14, lineHeight: "24px", color: "#1f2937" }}>
                {selectedItem?.value ?? "\u2014"}
              </p>
            </div>
          </div>

          <div
            className={showTranslatedDocument ? "edb-doc-readers-grid edb-doc-readers-two-col" : "edb-doc-readers-grid"}
          >
            <EvidenceDocumentReader
              title="Original document"
              paragraphs={originalDocument.paragraphs}
            />
            {showTranslatedDocument && (
              <EvidenceDocumentReader
                title="English translation"
                paragraphs={translatedDocument.paragraphs}
              />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export function EvidenceDetailView({
  groupId,
  initialEvidenceId,
  initialView = "overview",
}: EvidenceDetailViewProps) {
  const { detail, isLoading, error } = useEvidenceGroupDetail(groupId);
  const [selectedOverrideId, setSelectedOverrideId] = useState<string | null>(
    null,
  );

  const selectedEvidenceId = useMemo(() => {
    if (!detail) {
      return null;
    }
    if (
      selectedOverrideId &&
      detail.items.some(
        (item) => item.canonical_evidence_id === selectedOverrideId,
      )
    ) {
      return selectedOverrideId;
    }
    return findInitialEvidenceId(detail, initialEvidenceId);
  }, [detail, initialEvidenceId, selectedOverrideId]);

  if (isLoading) {
    return <EvidenceDetailSkeleton />;
  }

  if (error || !detail) {
    return (
      <>
        <style>{`
          .edb-detail-error {
            position: relative;
            overflow: hidden;
            border-radius: 12px;
            border: 1px solid #fecaca;
            background: linear-gradient(to bottom right, #fef2f2, #fff);
            padding: 56px 24px;
            text-align: center;
          }
        `}</style>
        <div className="edb-detail-error">
          <div style={{ position: "relative" }}>
            <div
              style={{
                margin: "0 auto",
                display: "flex",
                height: 56,
                width: 56,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 16,
                backgroundColor: "#fee2e2",
              }}
            >
              <AlertCircle style={{ width: 28, height: 28, color: "#ef4444" }} />
            </div>
            <p style={{ marginTop: 16, fontSize: 14, fontWeight: 600, color: "#991b1b" }}>
              Failed to load evidence detail
            </p>
            <p style={{ marginTop: 4, fontSize: 14, color: "#dc2626" }}>
              {error?.message ?? "The requested evidence group could not be found."}
            </p>
            <Link
              to="/evidence"
              style={{
                marginTop: 20,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                borderRadius: 6,
                backgroundColor: "#dc2626",
                padding: "8px 16px",
                fontSize: 14,
                fontWeight: 500,
                color: "#fff",
                textDecoration: "none",
                transition: "background-color 0.15s",
              }}
            >
              <ArrowLeft style={{ width: 16, height: 16 }} />
              Back to literature
            </Link>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <style>{`
        /* Responsive grids */
        .edb-overview-meta-grid {
          display: grid;
          gap: 0;
        }
        @media (min-width: 768px) {
          .edb-overview-meta-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }
        }
        .edb-overview-meta-cell {
          border-bottom: 1px solid #f3f4f6;
          padding: 16px 20px;
        }
        @media (min-width: 768px) {
          .edb-overview-meta-cell {
            border-bottom: none;
            border-right: 1px solid #f3f4f6;
          }
          .edb-overview-meta-cell:last-child {
            border-right: none;
          }
        }
        .edb-overview-layout {
          display: grid;
          gap: 20px;
        }
        @media (min-width: 1024px) {
          .edb-overview-layout {
            grid-template-columns: 300px minmax(0, 1fr);
          }
        }
        .edb-compare-stats-grid {
          display: grid;
          gap: 0;
        }
        @media (min-width: 640px) {
          .edb-compare-stats-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
          }
        }
        .edb-compare-stat-cell {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px;
          border-bottom: 1px solid #f3f4f6;
        }
        .edb-compare-stat-cell:last-child {
          border-bottom: none;
        }
        @media (min-width: 640px) {
          .edb-compare-stat-cell {
            border-bottom: none;
            border-right: 1px solid #f3f4f6;
          }
          .edb-compare-stat-cell:last-child {
            border-right: none;
          }
        }
        .edb-compare-layout {
          display: grid;
          gap: 20px;
        }
        @media (min-width: 1024px) {
          .edb-compare-layout {
            grid-template-columns: 340px minmax(0, 1fr);
          }
        }
        .edb-doc-readers-grid {
          display: grid;
          gap: 16px;
        }
        @media (min-width: 1280px) {
          .edb-doc-readers-grid.edb-doc-readers-two-col {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }

        /* Coverage stats 2-col grid borders */
        .edb-coverage-stat-cell {
          padding: 16px;
        }
        .edb-coverage-stat-cell:nth-child(odd) {
          border-right: 1px solid #f3f4f6;
        }
        .edb-coverage-stat-cell:nth-child(-n+2) {
          border-bottom: 1px solid #f3f4f6;
        }

        /* Line clamp */
        .edb-line-clamp-2 {
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        .edb-line-clamp-3 {
          display: -webkit-box;
          -webkit-line-clamp: 3;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        /* Card hover */
        .edb-evidence-card {
          position: relative;
          overflow: hidden;
          border-radius: 12px;
          border: 1px solid #e5e7eb;
          background: #fff;
          box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05);
          transition: all 0.15s;
        }
        .edb-evidence-card:hover {
          border-color: var(--color-primary-200, #a5f3fc);
          box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }
        .edb-evidence-card:hover .edb-evidence-card-accent {
          opacity: 1;
        }

        /* Back link hover */
        .edb-back-link:hover {
          color: var(--color-primary-600, #0891b2) !important;
        }

        /* Focus visible */
        .edb-focusable-link:focus-visible {
          outline: 2px solid var(--color-primary-500, #06b6d4);
          outline-offset: 0;
        }
        .edb-focusable-btn:focus-visible {
          outline: 2px solid var(--color-primary-500, #06b6d4);
          outline-offset: 0;
        }

        /* Navigator hover */
        .edb-nav-item:hover {
          border-color: #d1d5db !important;
          background-color: #f9fafb !important;
          box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05) !important;
        }
        .edb-nav-item:hover .edb-nav-item-title {
          color: var(--color-primary-700, #0e7490);
        }

        /* Toggle label hover */
        .edb-toggle-label:hover {
          background-color: #f9fafb;
        }
        /* Toggle input focus-visible */
        .edb-toggle-input:focus-visible ~ .edb-toggle-track {
          box-shadow: 0 0 0 2px var(--color-primary-500, #06b6d4), 0 0 0 4px #fff;
        }
      `}</style>
      {initialView === "compare" ? (
        <BilingualCompareView
          detail={detail!}
          groupId={groupId}
          selectedEvidenceId={selectedEvidenceId}
          setSelectedEvidenceId={setSelectedOverrideId}
        />
      ) : (
        <LiteratureOverview detail={detail!} groupId={groupId} />
      )}
    </>
  );
}
