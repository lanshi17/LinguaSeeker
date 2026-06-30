import { Link, useLocation } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Stethoscope,
  Layers3,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { useVariantDetail } from "../hooks/useVariantDetail";
import { VariantDetailSkeleton } from "./VariantDetailSkeleton";
import type { LiteratureReference, VariantIndexEntry, ClassificationLevel } from "../types/variantDb";
import type { EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";
import {
  classificationColor,
  classificationLabel,
} from "../utils/pathogenicity";
import {
  categoryLabel,
} from "@/features/evidence-search/utils/categoryStyles";
import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";
import {
  getEvidenceDbLabels,
  formatConfidencePercent,
  formatCoverageCount,
  formatReviewedCount,
} from "../utils/fieldLabels";
import { useI18n } from "@/lib/i18n";

/* ── Style helpers (replace Tailwind-based classificationBadgeClasses / categoryChipStyle) ── */

function badgeInlineStyle(level: ClassificationLevel): React.CSSProperties {
  const color = classificationColor(level);
  return {
    display: "inline-flex",
    alignItems: "center",
    borderRadius: 6,
    border: `1px solid ${color}40`,
    padding: "4px 10px",
    fontSize: 12,
    fontWeight: 600,
    backgroundColor: `${color}18`,
    color: color,
  };
}

function chipInlineStyle(category?: string | null): React.CSSProperties {
  const hex = category && CATEGORY_COLORS[category]
    ? CATEGORY_COLORS[category].hex
    : "#64748B";
  return {
    display: "inline-flex",
    alignItems: "center",
    borderRadius: 4,
    border: `1px solid ${hex}40`,
    padding: "2px 6px",
    fontSize: 10,
    fontWeight: 500,
    fontFamily: "var(--font-mono)",
    backgroundColor: `${hex}14`,
    color: hex,
  };
}

/* ── Embedded responsive styles ──────────────────────────── */

const embeddedCSS = `
.vdv-hero-inner {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
@media (min-width: 1024px) {
  .vdv-hero-inner {
    flex-direction: row;
    align-items: flex-start;
    justify-content: space-between;
  }
}
.vdv-main-grid {
  display: grid;
  gap: 24px;
  grid-template-columns: 1fr;
}
@media (min-width: 1024px) {
  .vdv-main-grid {
    grid-template-columns: minmax(0, 1fr) 340px;
  }
}
.vdv-back-link:hover {
  color: var(--color-text-strong);
}
.vdv-evidence-item:hover {
  border-color: var(--color-border);
}
.vdv-lit-card:hover {
  border-color: var(--color-primary-200);
  box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05);
}
.vdv-lit-card:hover .vdv-lit-title {
  color: var(--color-primary-700);
}
.vdv-lit-card:hover .vdv-lit-chevron {
  color: var(--color-primary-600);
}
`;

/* ── Confidence Ring ────────────────────────────────────── */

function ConfidenceRing({ value, size = 56 }: { value: number; size?: number }) {
  const pct = Math.round(value * 100);
  const ringColor = pct >= 70 ? "#22C55E" : pct >= 40 ? "#FFB323" : "#FF4D6D";
  return (
    <div
      className="edb-ring"
      style={
        {
          width: size,
          height: size,
          "--ring-value": pct,
          color: ringColor,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "50%",
        } as React.CSSProperties
      }
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "50%",
          backgroundColor: "var(--color-surface)",
          width: size - 8,
          height: size - 8,
        }}
      >
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "var(--color-code-text)" }}>
          {pct}%
        </span>
      </div>
    </div>
  );
}

/* ── Evidence Item Card ─────────────────────────────────── */

function EvidenceItemCard({ item, t }: { item: EvidenceGroupItem; t: (key: string, params?: Record<string, unknown>) => string }) {
  const cat = item.category ?? (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
  const catHex = cat ? CATEGORY_COLORS[cat]?.hex ?? "#64748B" : "#64748B";
  const confidence = item.confidence ?? 0;
  const confColor = confidence >= 0.7 ? "#16A34A" : confidence >= 0.4 ? "#D97706" : "#DC2626";

  return (
    <div className="vdv-evidence-item" style={{
      display: "flex",
      alignItems: "flex-start",
      gap: 12,
      borderRadius: 8,
      border: "1px solid var(--color-bg-muted)",
      backgroundColor: "var(--color-surface)",
      padding: 12,
      transition: "border-color 0.15s",
    }}>
      {/* Category accent */}
      <div
        style={{
          marginTop: 2,
          width: 4,
          height: 32,
          flexShrink: 0,
          borderRadius: 9999,
          backgroundColor: catHex,
        }}
      />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text)", lineHeight: 1.375, margin: 0 }}>
              {item.field_name ?? item.field_id}
            </p>
            {item.value && (
              <p style={{
                marginTop: 2,
                fontSize: 14,
                color: "var(--color-text-strong)",
                lineHeight: 1.625,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
                margin: 0,
                paddingTop: 2,
              }}>
                {typeof item.value === "string"
                  ? item.value
                  : JSON.stringify(item.value)}
              </p>
            )}
          </div>
          {cat && (
            <span
              style={{
                ...chipInlineStyle(cat),
                flexShrink: 0,
              }}
            >
              {cat}
            </span>
          )}
        </div>
        <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 12, fontSize: 11, color: "var(--color-text-secondary)" }}>
          <span style={{ fontFamily: "var(--font-mono)" }}>{item.field_id}</span>
          <span>&middot;</span>
          <span style={{ fontWeight: 500, color: confColor }}>
            {formatConfidencePercent(confidence)} {t("evidenceDb.card.confidence")}
          </span>
          {item.track && (
            <>
              <span>&middot;</span>
              <span style={{ textTransform: "capitalize" }}>{item.track}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Evidence Category Panel ────────────────────────────── */

function EvidenceCategoryPanel({
  items,
  category,
  t,
}: {
  items: EvidenceGroupItem[];
  category: string;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const hex = CATEGORY_COLORS[category]?.hex ?? "#64748B";
  const label = categoryLabel(category);
  const catItems = items.filter((item) => {
    const itemCat = item.category ?? (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
    return itemCat === category;
  });

  if (catItems.length === 0) return null;

  return (
    <div className="edb-card" style={{ borderRadius: 12, overflow: "hidden" }}>
      {/* Category header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 16px",
          borderBottom: "1px solid var(--color-border)",
          backgroundColor: `${hex}10`,
        }}
      >
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            backgroundColor: hex,
          }}
        />
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
          <span style={{ fontFamily: "var(--font-mono)" }}>{category}</span>: {label}
        </h3>
        <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-text-secondary)" }}>
          {t("evidenceDb.detail.fieldCount", { count: String(catItems.length) })}
        </span>
      </div>

      {/* Items */}
      <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
        {catItems.map((item) => (
          <EvidenceItemCard
            key={item.canonical_evidence_id}
            item={item}
            t={t}
          />
        ))}
      </div>
    </div>
  );
}

/* ── Literature Reference Card ──────────────────────────── */

function BilingualItemRow({
  fieldName,
  original,
  translated,
}: {
  fieldName: string;
  original?: string | null;
  translated?: string | null;
}) {
  return (
    <div style={{ fontSize: 12, lineHeight: 1.5 }}>
      <span style={{ fontWeight: 500, color: "var(--color-text-strong)" }}>{fieldName}</span>
      <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
        {original && (
          <span style={{
            flex: 1,
            color: "var(--color-blue-700)",
            background: "var(--color-blue-50)",
            borderRadius: 4,
            padding: "2px 6px",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}>
            {original}
          </span>
        )}
        {translated && (
          <span style={{
            flex: 1,
            color: "var(--color-purple-700)",
            background: "var(--color-highlight-purple)",
            borderRadius: 4,
            padding: "2px 6px",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}>
            {translated}
          </span>
        )}
      </div>
    </div>
  );
}

function LiteratureReferenceCard({
  reference,
  variantSlug,
  t,
}: {
  reference: LiteratureReference;
  variantSlug: string;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const confidence = Math.round(reference.avgConfidence * 100);
  const confColor = confidence >= 70 ? "#16A34A" : confidence >= 40 ? "#D97706" : "#DC2626";
  const bilingualEntries = [...reference.bilingualItems.entries()].slice(0, 3);

  return (
    <Link
      to={`/evidence-db/${encodeURIComponent(variantSlug)}/${encodeURIComponent(reference.sourceDocumentId)}`}
      className="vdv-lit-card"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        borderRadius: 8,
        border: "1px solid var(--color-bg-muted)",
        backgroundColor: "var(--color-surface)",
        padding: 12,
        transition: "all 0.15s",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div style={{
        display: "flex",
        width: 32,
        height: 32,
        flexShrink: 0,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 8,
        backgroundColor: "var(--color-highlight-amber)",
        color: "var(--color-warning-text)",
      }}>
        <BookOpen style={{ width: 16, height: 16 }} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <p className="vdv-lit-title" style={{
          fontSize: 14,
          fontWeight: 500,
          color: "var(--color-text)",
          lineHeight: 1.375,
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
          transition: "color 0.15s",
          margin: 0,
        }}>
          {reference.title}
        </p>
        <div style={{
          marginTop: 4,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          columnGap: 8,
          rowGap: 2,
          fontSize: 11,
          color: "var(--color-text-secondary)",
        }}>
          {reference.pmid && (
            <span style={{ fontFamily: "var(--font-mono)" }}>PMID:{reference.pmid}</span>
          )}
          {reference.doi && (
            <span style={{ fontFamily: "var(--font-mono)" }}>DOI:{reference.doi.slice(0, 20)}&hellip;</span>
          )}
          <span>{t("evidenceDb.detail.fieldCount", { count: String(reference.fieldCount) })}</span>
          <span style={{ fontWeight: 500, color: confColor }}>
            {confidence}%
          </span>
          <span>
            {formatReviewedCount(reference.reviewProgress, t)}
          </span>
        </div>
        <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {reference.hasFullText && (
            <span style={chipInlineStyle("F")}>{t("evidenceDb.detail.fullText")}</span>
          )}
          {reference.hasTranslation && (
            <span style={chipInlineStyle("I")}>{t("evidenceDb.detail.translated")}</span>
          )}
          {reference.conflictCount > 0 && (
            <span
              style={{
                borderRadius: 999,
                border: "1px solid var(--color-error-border)",
                backgroundColor: "var(--color-error-bg)",
                padding: "2px 6px",
                fontSize: 11,
                fontWeight: 500,
                color: "var(--color-error-text)",
              }}
            >
              {t("evidenceDb.bilingual.conflictCount", { count: String(reference.conflictCount) })}
            </span>
          )}
          {reference.categories.map((cat) => (
            <span
              key={cat}
              style={chipInlineStyle(cat)}
            >
              {cat}
            </span>
          ))}
        </div>
        {/* Bilingual items preview */}
        {bilingualEntries.length > 0 && (
          <div style={{
            marginTop: 8,
            paddingTop: 8,
            borderTop: "1px solid var(--color-bg-muted)",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}>
            <div style={{ display: "flex", gap: 8, fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>
              <span style={{ flex: 1, color: "var(--color-blue-700)" }}>{t("evidenceDb.detail.original")}</span>
              <span style={{ flex: 1, color: "var(--color-purple-700)" }}>{t("evidenceDb.detail.translatedLabel")}</span>
            </div>
            {bilingualEntries.map(([id, pair]) => (
              <BilingualItemRow
                key={id}
                fieldName={pair.original?.field_name ?? pair.translated?.field_name ?? id}
                original={pair.original?.value}
                translated={pair.translated?.value}
              />
            ))}
            {reference.bilingualItems.size > 3 && (
              <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                +{reference.bilingualItems.size - 3} more&hellip;
              </span>
            )}
          </div>
        )}
      </div>
      <ChevronRight className="vdv-lit-chevron" style={{
        width: 16,
        height: 16,
        flexShrink: 0,
        color: "var(--color-text-muted)",
        transition: "color 0.15s",
        marginTop: 4,
      }} />
    </Link>
  );
}

/* ── Main View ──────────────────────────────────────────── */

export function VariantDetailView({
  variantSlug,
}: {
  variantSlug: string;
}) {
  const { t } = useI18n();
  const labels = getEvidenceDbLabels(t);
  const location = useLocation();
  const routeState = location.state as { variantEntry?: VariantIndexEntry } | null;
  const seededEntry =
    routeState?.variantEntry?.variantSlug === variantSlug
      ? routeState.variantEntry
      : undefined;
  const { detail, isLoading, error } = useVariantDetail(variantSlug, seededEntry);

  if (isLoading) {
    return <VariantDetailSkeleton />;
  }

  if (error || !detail) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Link
          to="/evidence-db"
          className="vdv-back-link"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 14,
            color: "var(--color-text-secondary)",
            textDecoration: "none",
          }}
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          {t("evidenceDb.detail.back")}
        </Link>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          borderRadius: 12,
          border: "1px solid var(--color-error-border)",
          backgroundColor: "var(--color-error-bg)",
          padding: 16,
          fontSize: 14,
          color: "var(--color-error-text)",
        }}>
          <AlertCircle style={{ width: 20, height: 20, flexShrink: 0 }} />
          <span>{t("evidenceDb.detail.notFound")}</span>
        </div>
      </div>
    );
  }

  const { entry, literature, reconciledItems, quality } = detail;
  const borderColor = classificationColor(entry.classificationLevel);

  const categoriesWithItems = [
    ...new Set(
      reconciledItems.map(
        (item) =>
          item.category ??
          (item.field_id.includes(".") ? item.field_id.split(".")[0] : null),
      ),
    ),
  ]
    .filter(Boolean)
    .sort() as string[];

  return (
    <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <style>{embeddedCSS}</style>

      {/* Back navigation */}
      <Link
        to="/evidence-db"
        className="vdv-back-link"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontSize: 14,
          color: "var(--color-text-secondary)",
          textDecoration: "none",
          transition: "color 0.15s",
        }}
      >
        <ArrowLeft style={{ width: 16, height: 16 }} />
        {t("evidenceDb.detail.back")}
      </Link>

      {/* Variant Hero */}
      <section
        className="edb-hero"
        style={{
          borderRadius: 16,
          border: "1px solid var(--color-border)",
          borderLeftColor: borderColor,
          borderLeftWidth: 4,
          overflow: "hidden",
        }}
      >
        <div style={{ padding: 24 }}>
          <div className="vdv-hero-inner">
            {/* Main info */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                <h1 style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 20,
                  fontWeight: 700,
                  color: "var(--color-text)",
                  margin: 0,
                }}>
                  {entry.gene}
                </h1>
                <span style={badgeInlineStyle(entry.classificationLevel)}>
                  {classificationLabel(entry.classificationLevel)}
                </span>
              </div>
              <p style={{
                fontFamily: "var(--font-mono)",
                fontSize: 18,
                color: "var(--color-text-strong)",
                marginBottom: 4,
                margin: 0,
                paddingBottom: 4,
              }}>
                {entry.variant}
              </p>
              {entry.disease && (
                <p style={{ fontSize: 14, color: "var(--color-text-strong)", margin: 0 }}>
                  <Stethoscope style={{ display: "inline", width: 16, height: 16, marginRight: 4, verticalAlign: "-2px", color: "var(--color-text-muted)" }} />
                  {entry.disease}
                </p>
              )}
              {entry.classification && (
                <p style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 4, margin: 0 }}>
                  {entry.classification}
                </p>
              )}
              {quality.conflictCount > 0 && (
                <span
                  style={{
                    marginTop: 10,
                    display: "inline-flex",
                    alignItems: "center",
                    borderRadius: 6,
                    border: "1px solid var(--color-error-border)",
                    backgroundColor: "var(--color-error-bg)",
                    padding: "3px 8px",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--color-error-text)",
                  }}
                >
                  {t("evidenceDb.detail.conflicts")}
                </span>
              )}
            </div>

            {/* Stats */}
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <ConfidenceRing value={entry.avgConfidence} size={56} />
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, 1fr)",
                columnGap: 24,
                rowGap: 4,
              }}>
                <div>
                  <p style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                    {entry.literatureCount}
                  </p>
                  <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0 }}>{labels.literature}</p>
                </div>
                <div>
                  <p style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                    {entry.fieldCount}
                  </p>
                  <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0 }}>{labels.evidenceFields}</p>
                </div>
                <div>
                  <p style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                    {formatCoverageCount(quality.coverage)}
                  </p>
                  <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0 }}>{labels.coverage}</p>
                </div>
                <div>
                  <p style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                    {quality.reviewProgress.reviewed}/{quality.reviewProgress.total}
                  </p>
                  <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0 }}>{labels.reviewed}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Two-column layout: Evidence + Literature */}
      <div className="vdv-main-grid">
        {/* Main: Evidence by Category */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 style={{
              fontFamily: "var(--font-display)",
              fontSize: 18,
              fontWeight: 500,
              color: "var(--color-text)",
              margin: 0,
            }}>
              {t("evidenceDb.detail.evidenceFields")}
            </h2>
            <span style={{ fontSize: 14, color: "var(--color-text-secondary)" }}>
              {t("evidenceDb.detail.reconciled", { fields: String(reconciledItems.length), categories: String(categoriesWithItems.length) })}
            </span>
          </div>

          {categoriesWithItems.length === 0 ? (
            <div style={{
              borderRadius: 12,
              border: "1px dashed var(--color-text-muted)",
              padding: "48px 0",
              textAlign: "center",
            }}>
              <Layers3 style={{ width: 32, height: 32, color: "var(--color-text-muted)", margin: "0 auto 8px" }} />
              <p style={{ fontSize: 14, color: "var(--color-text-secondary)", margin: 0 }}>
                {t("evidenceDb.detail.noFields")}
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {categoriesWithItems.map((cat) => (
                <EvidenceCategoryPanel
                  key={cat}
                  items={reconciledItems}
                  category={cat}
                  t={t}
                />
              ))}
            </div>
          )}
        </div>

        {/* Sidebar: Literature References */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 style={{
              fontFamily: "var(--font-display)",
              fontSize: 18,
              fontWeight: 500,
              color: "var(--color-text)",
              margin: 0,
            }}>
              {t("evidenceDb.detail.references")}
            </h2>
            <span style={{ fontSize: 14, color: "var(--color-text-secondary)" }}>
              {t("evidenceDb.detail.sources", { count: String(literature.length) })}
            </span>
          </div>

          {literature.length === 0 ? (
            <div style={{
              borderRadius: 12,
              border: "1px dashed var(--color-text-muted)",
              padding: "48px 0",
              textAlign: "center",
            }}>
              <BookOpen style={{ width: 32, height: 32, color: "var(--color-text-muted)", margin: "0 auto 8px" }} />
              <p style={{ fontSize: 14, color: "var(--color-text-secondary)", margin: 0 }}>{t("evidenceDb.detail.noRefs")}</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {literature.map((ref) => (
                <LiteratureReferenceCard
                  key={ref.sourceDocumentId}
                  reference={ref}
                  variantSlug={variantSlug}
                  t={t}
                />
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
