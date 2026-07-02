import { STATUS_VARIANT } from "@/lib/constants/statusVariant";
import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { Button } from "antd";
import {
  ArrowLeft,
  BookOpen,
  Columns2,
  Database,
  Download,
  Dna,
  FileText,
  FlaskConical,
  Hash,
  Languages,
  Layers3,
  Link2,
  ListChecks,
  Percent,
  Pencil,
  Search,
  ShieldCheck,
  Stethoscope,
  TrendingUp,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/Badge";
import { EvidenceCorrectionForm } from "./EvidenceCorrectionForm";
import { EvidenceAuditHistory } from "./EvidenceAuditHistory";
import { ExportReportDrawer } from "./ExportReportDrawer";
import type {
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
} from "../types/evidenceSearch";
import { CATEGORY_COLORS } from "../utils/evidenceDocument";
import { categoryLabel } from "../utils/categoryStyles";
import { buildBilingualCompareHref } from "../utils/literatureRows";

/* ---- Inline style helpers ---- */

export function chipInlineStyle(hex?: string): React.CSSProperties {
  if (!hex) return { borderColor: "var(--color-border)", backgroundColor: "var(--color-bg)", color: "var(--color-text-strong)" };
  return { borderColor: hex + "60", backgroundColor: hex + "15", color: hex };
}

/* ---- Constants ---- */

/* ---- Utility functions ---- */

export function formatPercent(value?: number | null) {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

export function categoryFromItem(item?: EvidenceGroupItem | null) {
  if (!item) {
    return null;
  }
  if (item.category) {
    return item.category;
  }
  return item.field_id.includes(".") ? item.field_id.split(".", 1)[0] : null;
}

export function itemLabel(item: EvidenceGroupItem) {
  return item.field_name ?? item.field_id;
}

function countEntries(record: Record<string, number>) {
  return Object.entries(record).sort(([a], [b]) => a.localeCompare(b));
}

export function detailTitle(detail: EvidenceGroupDetailResponse) {
  const title = detail.title?.trim();
  return title || "Untitled literature record";
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
        backgroundColor: "var(--color-bg)",
        padding: "4px 8px",
        fontSize: 12,
      }}
    >
      <Icon style={{ width: 14, height: 14, color: "var(--color-text-muted)" }} />
      <span style={{ fontWeight: 500, color: "var(--color-text-strong)" }}>{value}</span>
      <span style={{ color: "var(--color-text-secondary)" }}>{label}</span>
    </div>
  );
}

export function MetadataToken({
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
        border: "1px solid var(--color-primary-200)",
        backgroundColor: "var(--color-surface)",
        padding: "4px 10px",
        fontSize: 12,
        color: "var(--color-primary-900, var(--color-primary-900))",
      }}
    >
      {Icon && <Icon style={{ width: 12, height: 12, flexShrink: 0, color: "var(--color-primary-500, var(--color-primary-500))" }} />}
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

export function EvidenceTonePill({ item }: { item: EvidenceGroupItem }) {
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

function EvidenceItemSummary({
  groupId,
  item,
}: {
  groupId: string;
  item: EvidenceGroupItem;
}) {
  const [editing, setEditing] = useState(false);
  const cardField = cardFieldForFieldId(item.field_id);
  const { t } = useI18n();

  return (
    <article className="edb-evidence-card">
      <div style={{ padding: 16 }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
              <EvidenceTonePill item={item} />
              <Badge variant={STATUS_VARIANT[item.review_status as keyof typeof STATUS_VARIANT] ?? "default"}>
                {item.review_status}
              </Badge>
            </div>
            <h3 style={{ marginTop: 12, fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>
              {itemLabel(item)}
            </h3>
            <p style={{ marginTop: 4, fontFamily: "monospace", fontSize: 12, color: "var(--color-text-secondary)" }}>
              {item.field_id}
            </p>
          </div>
          <div className="no-print" style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
                      borderColor: "var(--color-border)",
                      backgroundColor: "var(--color-surface)",
                      color: "var(--color-text-strong)",
                    }),
              }}
            >
              <Pencil style={{ width: 14, height: 14 }} />
              {editing ? t("evidence.lit.close") : t("evidence.lit.edit")}
            </button>
            <Link
              to={buildBilingualCompareHref(groupId, item.canonical_evidence_id)}
              className="edb-focusable-link"
              style={{
                display: "inline-flex",
                height: 36,
                cursor: "pointer",
                alignItems: "center",
                gap: 6,
                borderRadius: 6,
                border: "1px solid var(--color-primary-600)",
                backgroundColor: "transparent",
                padding: "0 10px",
                fontSize: 13,
                fontWeight: 500,
                color: "var(--color-primary-600)",
                textDecoration: "none",
                transition: "background-color 0.15s",
              }}
            >
              <Columns2 style={{ width: 16, height: 16 }} />
              {t("evidence.lit.compare")}
            </Link>
          </div>
        </div>

        <p className="edb-line-clamp-3" style={{ marginTop: 16, fontSize: 14, lineHeight: "24px", color: "var(--color-text-strong)" }}>
          {item.value ?? "\u2014"}
        </p>

        <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 8, borderTop: "1px solid var(--color-bg-muted)", paddingTop: 12 }}>
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

/* ---- LiteratureOverview ---- */

export function LiteratureOverview({
  detail,
  groupId,
}: {
  detail: EvidenceGroupDetailResponse;
  groupId: string;
}) {
  const [exportOpen, setExportOpen] = useState(false);
  const { t } = useI18n();

  return (
    <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Print-only report header — hidden on screen, visible in print */}
      <div className="print-only">
        <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--color-text)", margin: 0 }}>
          {t("evidence.lit.reportHeader")}
        </h1>
        <p style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: "8px 0 4px" }}>
          {detailTitle(detail)}
        </p>
        <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0 }}>
          {detail.pmid && `PMID: ${detail.pmid}`}
          {detail.pmid && detail.doi && " · "}
          {detail.doi && `DOI: ${detail.doi}`}
        </p>
        <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: "4px 0 0" }}>
          {t("evidence.lit.generated")} {new Date().toLocaleString()}
        </p>
        <hr style={{ margin: "16px 0", border: "none", borderTop: "1px solid var(--color-border)" }} />
      </div>
      <Link
        to="/evidence"
        className="edb-back-link no-print"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          fontSize: 14,
          fontWeight: 500,
          color: "var(--color-text-secondary)",
          textDecoration: "none",
          transition: "color 0.15s",
        }}
      >
        <ArrowLeft style={{ width: 16, height: 16 }} />
        {t("evidence.lit.back")}
      </Link>

      <section style={{ overflow: "hidden", borderRadius: 8, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)" }}>
        <div
          style={{
            borderBottom: "1px solid var(--color-border)",
            padding: "16px 20px",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
            <div style={{ minWidth: 0 }}>
              <p
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 10,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "var(--color-text-secondary)",
                  margin: 0,
                }}
              >
                <BookOpen style={{ width: 14, height: 14 }} />
                {t("evidence.lit.recordLabel")}
              </p>
              <h2 style={{ marginTop: 6, maxWidth: 896, fontSize: 16, fontWeight: 600, lineHeight: "24px", color: "var(--color-text)" }}>
                {detailTitle(detail)}
              </h2>
              <div style={{ marginTop: 10, display: "flex", maxWidth: 896, flexWrap: "wrap", gap: 8 }}>
                <MetadataToken label={t("evidence.lit.uuid")} value={detail.source_document_id} icon={Hash} />
                <MetadataToken label={t("evidence.lit.pmid")} value={detail.pmid} icon={FileText} />
                <MetadataToken label={t("evidence.lit.doi")} value={detail.doi} icon={Link2} />
              </div>
            </div>
            <div className="edb-overview-actions" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Badge variant={STATUS_VARIANT.approved}>{t("evidence.lit.traceable")}</Badge>
              <Button
                className="no-print"
                icon={<Download style={{ width: 16, height: 16 }} />}
                onClick={() => setExportOpen(true)}
              >
                {t("evidence.lit.export")}
              </Button>
            </div>
          </div>
        </div>

        <div className="edb-overview-meta-grid">
          {(
            [
              { label: t("evidence.lit.gene"), value: detail.gene, Icon: Dna },
              { label: t("evidence.lit.variant"), value: detail.variant, Icon: FlaskConical },
              { label: t("evidence.lit.disease"), value: detail.disease, Icon: Stethoscope },
              { label: t("evidence.lit.classification"), value: detail.classification, Icon: ShieldCheck },
            ] as const
          ).map(({ label, value, Icon }) => (
            <div key={label} className="edb-overview-meta-cell">
              <p
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 10,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "var(--color-text-muted)",
                  margin: 0,
                }}
              >
                <Icon style={{ width: 12, height: 12 }} />
                {label}
              </p>
              <p className="edb-line-clamp-3" style={{ marginTop: 6, fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>
                {value ?? "\u2014"}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="edb-overview-layout">
        <aside style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <section style={{ borderRadius: 8, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)" }}>
            <div style={{ borderBottom: "1px solid var(--color-border)", padding: "10px 16px" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: 0 }}>
                <ListChecks style={{ width: 14, height: 14, color: "var(--color-primary-600)" }} />
                {t("evidence.lit.coverage")}
              </h3>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
              {[
                { label: t("evidence.lit.items"), value: detail.item_count, icon: Database },
                { label: t("evidence.lit.confidence"), value: formatPercent(detail.avg_confidence), icon: TrendingUp },
                { label: t("evidence.lit.traces"), value: detail.traces.length, icon: Search },
                { label: t("evidence.lit.fields"), value: Object.keys(detail.distribution.by_field).length, icon: FileText },
              ].map((stat) => (
                <div key={stat.label} className="edb-coverage-stat-cell">
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <stat.icon style={{ width: 14, height: 14, color: "var(--color-text-muted)" }} />
                    <p style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-secondary)", margin: 0 }}>{stat.label}</p>
                  </div>
                  <p style={{ marginTop: 4, fontSize: 16, fontWeight: 600, fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums", color: "var(--color-text)" }}>
                    {stat.value}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section style={{ borderRadius: 8, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)" }}>
            <div style={{ borderBottom: "1px solid var(--color-border)", padding: "10px 16px" }}>
              <h3 style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: 0 }}>
                {t("evidence.lit.categories")}
              </h3>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: 16 }}>
              {countEntries(detail.distribution.by_category).map(([key, count]) => (
                <span
                  key={key}
                  style={{
                    borderRadius: 6,
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-bg)",
                    padding: "6px 10px",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--color-text-strong)",
                  }}
                >
                  {categoryLabel(key)} · {count}
                </span>
              ))}
            </div>
          </section>

          <section style={{ borderRadius: 8, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)" }}>
            <div style={{ borderBottom: "1px solid var(--color-border)", padding: "10px 16px" }}>
              <h3 style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: 0 }}>
                {t("evidence.lit.reviewStatus")}
              </h3>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: 16 }}>
              {countEntries(detail.distribution.by_status).map(([key, count]) => (
                <Badge key={key} variant={STATUS_VARIANT[key as keyof typeof STATUS_VARIANT] ?? "default"}>
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
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              padding: "12px 16px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  display: "flex",
                  height: 36,
                  width: 36,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  color: "var(--color-primary-600)",
                }}
              >
                <ListChecks style={{ width: 16, height: 16 }} />
              </div>
              <div>
                <h2 style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: 0 }}>
                  {t("evidence.lit.extractedFields")}
                </h2>
                <p style={{ marginTop: 2, fontSize: 13, color: "var(--color-text-secondary)" }}>
                  {t("evidence.lit.fieldCount", { count: detail.items.length })}
                </p>
              </div>
            </div>
            {detail.items[0] && (
              <Link
                to={buildBilingualCompareHref(groupId, detail.items[0].canonical_evidence_id)}
                className="edb-focusable-link no-print"
                style={{
                  display: "inline-flex",
                  height: 36,
                  cursor: "pointer",
                  alignItems: "center",
                  gap: 6,
                  borderRadius: 6,
                  border: "1px solid var(--color-primary-600)",
                  backgroundColor: "transparent",
                  padding: "0 12px",
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--color-primary-600)",
                  textDecoration: "none",
                  transition: "background-color 0.15s",
                }}
              >
                <Languages style={{ width: 14, height: 14 }} />
                {t("evidence.lit.compare")}
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

      <ExportReportDrawer
        detail={detail}
        open={exportOpen}
        onClose={() => setExportOpen(false)}
      />
    </div>
  );
}
