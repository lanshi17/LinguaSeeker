import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Languages,
  ExternalLink,
  AlertCircle,
  ChevronRight,
  Eye,
  EyeOff,
} from "lucide-react";
import { useEvidenceGroupDetail } from "@/features/evidence-search/hooks/useEvidenceGroupDetail";
import type { EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";
import {
  CATEGORY_COLORS,
  EVIDENCE_CATEGORIES,
  buildEvidenceDocument,
  hasTranslatedDocumentText,
  countEvidenceCategories,
} from "@/features/evidence-search/utils/evidenceDocument";
import {
  categoryLabel,
} from "@/features/evidence-search/utils/categoryStyles";
import type {
  EvidenceDocument,
  EvidenceDocumentParagraph,
} from "@/features/evidence-search/utils/evidenceDocument";
import { useVariantDetail } from "../hooks/useVariantDetail";
import { BilingualEvidenceSkeleton } from "./BilingualEvidenceSkeleton";

/* ── Style helpers (replace Tailwind-based categoryMarkStyle / categoryChipStyle) ── */

function markInlineStyle(category?: string | null, selected?: boolean): React.CSSProperties {
  const hex = category && CATEGORY_COLORS[category]
    ? CATEGORY_COLORS[category].hex
    : "#9CA3AF";
  const base: React.CSSProperties = {
    backgroundColor: `${hex}50`,
    color: `${hex}f0`,
    boxShadow: `0 0 0 1px ${hex}60`,
    borderRadius: 2,
    padding: "0 2px",
    cursor: "help",
    transition: "all 0.15s",
  };
  if (selected) {
    base.boxShadow = `0 0 0 2px var(--color-primary-500), 0 0 0 3px white, 0 0 0 1px ${hex}60`;
  }
  return base;
}

/* ── Embedded responsive styles ──────────────────────────── */

const embeddedCSS = `
.bev-main-grid {
  display: grid;
  gap: 20px;
}
@media (min-width: 1024px) {
  .bev-main-grid {
    grid-template-columns: 280px minmax(0, 1fr);
  }
}
.bev-bilingual-grid {
  display: grid;
  gap: 16px;
}
@media (min-width: 1024px) {
  .bev-bilingual-grid.bev-bilingual-grid--dual {
    grid-template-columns: 1fr 1fr;
  }
}
.bev-link:hover {
  color: #4b5563;
}
.bev-pmid-link:hover {
  color: var(--color-primary-700);
}
.bev-eye-btn:hover {
  color: #4b5563;
  background-color: #f3f4f6;
}
.bev-nav-item:hover {
  background-color: #f9fafb;
}
.bev-nav-item--selected {
  background-color: var(--color-primary-50);
  border: 1px solid var(--color-primary-200);
}
`;

/* ── Highlighted Text Renderer ──────────────────────────── */

function HighlightedText({ paragraph }: { paragraph: EvidenceDocumentParagraph }) {
  const sorted = useMemo(
    () => [...paragraph.highlights].sort((a, b) => a.start - b.start),
    [paragraph.highlights],
  );
  if (sorted.length === 0) {
    return (
      <p style={{
        fontSize: 14,
        lineHeight: 1.625,
        color: "#374151",
        whiteSpace: "pre-wrap",
        margin: 0,
      }}>
        {paragraph.text}
      </p>
    );
  }

  const segments: React.ReactNode[] = [];
  let cursor = 0;

  for (const hl of sorted) {
    const start = Math.max(0, Math.min(hl.start, paragraph.text.length));
    const end = Math.max(start, Math.min(hl.end, paragraph.text.length));
    if (start > end) continue;

    if (cursor < start) {
      segments.push(
        <span key={`plain-${cursor}`}>
          {paragraph.text.slice(cursor, start)}
        </span>,
      );
    }

    segments.push(
      <mark
        key={`hl-${hl.evidenceId}-${start}`}
        style={markInlineStyle(hl.category, hl.selected)}
        title={`${hl.label} (${hl.fieldId})`}
      >
        {paragraph.text.slice(start, end)}
      </mark>,
    );
    cursor = end;
  }

  if (cursor < paragraph.text.length) {
    segments.push(
      <span key={`tail-${cursor}`}>{paragraph.text.slice(cursor)}</span>,
    );
  }

  return (
    <p style={{
      fontSize: 14,
      lineHeight: 1.625,
      color: "#374151",
      whiteSpace: "pre-wrap",
      margin: 0,
    }}>
      {segments}
    </p>
  );
}

/* ── Document Reader Panel ──────────────────────────────── */

function DocumentReader({
  title,
  track,
  document,
  accentColor,
}: {
  title: string;
  track: "original" | "translated";
  document: EvidenceDocument;
  accentColor: string;
}) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      borderRadius: 12,
      border: "1px solid #e5e7eb",
      backgroundColor: "#fff",
      overflow: "hidden",
    }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 16px",
          borderBottom: "1px solid #f3f4f6",
          backgroundColor: `${accentColor}08`,
        }}
      >
        <Languages style={{ width: 16, height: 16, color: accentColor }} />
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "#1f2937", margin: 0 }}>{title}</h3>
        <span style={{
          marginLeft: "auto",
          fontSize: 11,
          textTransform: "capitalize",
          color: "#6b7280",
        }}>
          {track} track
        </span>
      </div>
      <div className="edb-scroll" style={{ maxHeight: 600, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        {document.paragraphs.length === 0 ? (
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "48px 0",
            textAlign: "center",
          }}>
            <BookOpen style={{ width: 32, height: 32, color: "#9ca3af", marginBottom: 8 }} />
            <p style={{ fontSize: 14, color: "#6b7280", margin: 0 }}>
              No {track} text available
            </p>
          </div>
        ) : (
          document.paragraphs.map((para) => (
            <div key={para.id} style={{ position: "relative" }}>
              {para.page && (
                <span style={{
                  position: "absolute",
                  left: -8,
                  top: 0,
                  fontSize: 10,
                  color: "#9ca3af",
                  fontFamily: "var(--font-mono)",
                }}>
                  p.{para.page}
                </span>
              )}
              <HighlightedText paragraph={para} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ── Category Toggle ────────────────────────────────────── */

function CategoryToggle({
  category,
  count,
  checked,
  onChange,
}: {
  category: string;
  count: number;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const hex = CATEGORY_COLORS[category]?.hex ?? "#64748B";

  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        borderRadius: 8,
        border: checked ? "1px solid #e5e7eb" : "1px solid transparent",
        backgroundColor: checked ? "#fff" : "#f9fafb",
        opacity: checked ? 1 : 0.5,
        padding: "6px 10px",
        fontSize: 12,
        fontWeight: 500,
        cursor: "pointer",
        transition: "all 0.15s",
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{
          position: "absolute",
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
          whiteSpace: "nowrap",
          borderWidth: 0,
        }}
      />
      <div
        style={{
          display: "flex",
          width: 16,
          height: 16,
          flexShrink: 0,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 4,
          border: checked ? "1px solid transparent" : "1px solid #d1d5db",
          backgroundColor: checked ? hex : "#fff",
          color: checked ? "#0f172a" : undefined,
          transition: "background-color 0.15s",
        }}
      >
        {checked && (
          <svg style={{ width: 12, height: 12 }} viewBox="0 0 12 12" fill="none">
            <path
              d="M2 6l3 3 5-5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>
      <span style={{ color: "#374151" }}>
        <span style={{ fontFamily: "var(--font-mono)" }}>{category}</span>: {categoryLabel(category)}
      </span>
      <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", color: "#6b7280" }}>{count}</span>
    </label>
  );
}

/* ── Evidence Navigator ─────────────────────────────────── */

function EvidenceNavigator({
  items,
  selectedId,
  onSelect,
}: {
  items: EvidenceGroupItem[];
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {items.map((item) => {
        const cat =
          item.category ??
          (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
        const hex = cat ? CATEGORY_COLORS[cat]?.hex ?? "#64748B" : "#64748B";
        const isSelected = item.canonical_evidence_id === selectedId;
        const confidence = item.confidence ?? 0;
        const confColor = confidence >= 0.7 ? "#059669" : confidence >= 0.4 ? "#D97706" : "#EF4444";

        return (
          <button
            key={item.canonical_evidence_id}
            type="button"
            onClick={() => onSelect(item.canonical_evidence_id)}
            className={isSelected ? "bev-nav-item bev-nav-item--selected" : "bev-nav-item"}
            style={{
              display: "flex",
              width: "100%",
              alignItems: "center",
              gap: 8,
              borderRadius: 8,
              padding: "8px 10px",
              textAlign: "left",
              fontSize: 12,
              transition: "all 0.15s",
              cursor: "pointer",
              border: isSelected ? undefined : "1px solid transparent",
              backgroundColor: isSelected ? undefined : undefined,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                flexShrink: 0,
                borderRadius: "50%",
                backgroundColor: hex,
              }}
            />
            <span style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
              color: "#374151",
              fontWeight: 500,
            }}>
              {item.field_name ?? item.field_id}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: confColor }}>
              {Math.round(confidence * 100)}%
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Active Evidence Card ───────────────────────────────── */

function ActiveEvidenceCard({ item }: { item: EvidenceGroupItem }) {
  const cat =
    item.category ??
    (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
  const hex = cat ? CATEGORY_COLORS[cat]?.hex ?? "#64748B" : "#64748B";
  const confidence = item.confidence ?? 0;
  const confColor = confidence >= 0.7 ? "#059669" : confidence >= 0.4 ? "#D97706" : "#EF4444";

  return (
    <div
      style={{
        borderRadius: 12,
        border: "1px solid #e5e7eb",
        borderLeftColor: hex,
        borderLeftWidth: 3,
        backgroundColor: "#fff",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
              {item.field_name ?? item.field_id}
            </p>
            <p style={{ fontSize: 11, color: "#6b7280", fontFamily: "var(--font-mono)", marginTop: 2, margin: 0 }}>
              {item.field_id}
            </p>
          </div>
          {cat && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                borderRadius: 4,
                border: `1px solid ${hex}40`,
                padding: "2px 6px",
                fontSize: 10,
                fontWeight: 500,
                backgroundColor: `${hex}1a`,
                color: hex,
              }}
            >
              <span style={{ fontFamily: "var(--font-mono)" }}>{cat}</span>: {categoryLabel(cat)}
            </span>
          )}
        </div>

        {item.value && (
          <div style={{ borderRadius: 8, backgroundColor: "#f9fafb", padding: 12, marginBottom: 8 }}>
            <p style={{ fontSize: 14, color: "#374151", lineHeight: 1.625, margin: 0 }}>
              {typeof item.value === "string"
                ? item.value
                : JSON.stringify(item.value, null, 2)}
            </p>
          </div>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 11, color: "#6b7280" }}>
          <span style={{ fontWeight: 500, color: confColor }}>
            {Math.round(confidence * 100)}% confidence
          </span>
          <span>&middot;</span>
          <span style={{ textTransform: "capitalize" }}>{item.track ?? "original"}</span>
          {item.page && (
            <>
              <span>&middot;</span>
              <span>Page {item.page}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Main View ──────────────────────────────────────────── */

export function BilingualEvidenceView({
  variantSlug,
  sourceDocumentId,
}: {
  variantSlug: string;
  sourceDocumentId: string;
}) {
  const [enabledCategories, setEnabledCategories] = useState<Set<string>>(
    () => new Set(EVIDENCE_CATEGORIES),
  );
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<
    string | undefined
  >(undefined);

  const { detail: variantDetail, isLoading: isVariantLoading } =
    useVariantDetail(variantSlug);

  const groupId = useMemo(() => {
    if (!variantDetail) return null;
    const group = variantDetail.evidenceGroups.find(
      (g) => g.source_document_id === sourceDocumentId,
    );
    return group?.group_id ?? variantDetail.entry.groupIds[0] ?? null;
  }, [variantDetail, sourceDocumentId]);

  const {
    detail: groupDetail,
    isLoading: isGroupLoading,
    error,
  } = useEvidenceGroupDetail(groupId ?? "");

  const isLoading = isVariantLoading || isGroupLoading;

  const originalDoc = useMemo(
    () =>
      groupDetail
        ? buildEvidenceDocument(
            groupDetail,
            "original",
            undefined,
            selectedEvidenceId,
            enabledCategories,
          )
        : null,
    [groupDetail, selectedEvidenceId, enabledCategories],
  );

  const translatedDoc = useMemo(
    () =>
      groupDetail
        ? buildEvidenceDocument(
            groupDetail,
            "translated",
            undefined,
            selectedEvidenceId,
            enabledCategories,
          )
        : null,
    [groupDetail, selectedEvidenceId, enabledCategories],
  );

  const hasTranslation = groupDetail
    ? hasTranslatedDocumentText(groupDetail)
    : false;

  const categoryCounts = useMemo(
    () => (groupDetail ? countEvidenceCategories(groupDetail.items) : {}),
    [groupDetail],
  );

  const toggleCategory = (cat: string) => {
    setEnabledCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  };

  const toggleAllCategories = (on: boolean) => {
    setEnabledCategories(on ? new Set(EVIDENCE_CATEGORIES) : new Set());
  };

  if (isLoading) {
    return <BilingualEvidenceSkeleton />;
  }

  if (error || !groupDetail) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Link
          to={`/evidence-db/${encodeURIComponent(variantSlug)}`}
          className="bev-link"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 14,
            color: "#9ca3af",
            textDecoration: "none",
          }}
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          Back to variant detail
        </Link>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          borderRadius: 12,
          border: "1px solid #fecaca",
          backgroundColor: "#fef2f2",
          padding: 16,
          fontSize: 14,
          color: "#b91c1c",
        }}>
          <AlertCircle style={{ width: 20, height: 20, flexShrink: 0 }} />
          <span>Failed to load evidence data for this literature.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <style>{embeddedCSS}</style>

      {/* Breadcrumb */}
      <nav style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, color: "#9ca3af" }}>
        <Link
          to="/evidence-db"
          className="bev-link"
          style={{ color: "inherit", textDecoration: "none" }}
        >
          Evidence DB
        </Link>
        <ChevronRight style={{ width: 14, height: 14 }} />
        <Link
          to={`/evidence-db/${encodeURIComponent(variantSlug)}`}
          className="bev-link"
          style={{ color: "inherit", textDecoration: "none", fontFamily: "var(--font-mono)" }}
        >
          {variantSlug.split(":").slice(0, 2).join(":")}
        </Link>
        <ChevronRight style={{ width: 14, height: 14 }} />
        <span style={{
          color: "#9ca3af",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          maxWidth: 300,
        }}>
          {groupDetail.title ?? "Literature"}
        </span>
      </nav>

      {/* Literature Header */}
      <section style={{
        borderRadius: 12,
        border: "1px solid #e5e7eb",
        backgroundColor: "#fff",
        padding: 20,
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
          <div style={{
            display: "flex",
            width: 40,
            height: 40,
            flexShrink: 0,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 8,
            backgroundColor: "#fffbeb",
            color: "#d97706",
          }}>
            <BookOpen style={{ width: 20, height: 20 }} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h1 style={{
              fontFamily: "var(--font-display)",
              fontSize: 18,
              fontWeight: 500,
              color: "#111827",
              lineHeight: 1.375,
              margin: 0,
            }}>
              {groupDetail.title ?? "Untitled Document"}
            </h1>
            <div style={{
              marginTop: 6,
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              columnGap: 12,
              rowGap: 4,
              fontSize: 12,
              color: "#6b7280",
            }}>
              {groupDetail.pmid && (
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${groupDetail.pmid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bev-pmid-link"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    fontFamily: "var(--font-mono)",
                    color: "var(--color-primary-600)",
                    textDecoration: "none",
                  }}
                >
                  PMID:{groupDetail.pmid}
                  <ExternalLink style={{ width: 12, height: 12 }} />
                </a>
              )}
              {groupDetail.doi && (
                <a
                  href={`https://doi.org/${groupDetail.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bev-pmid-link"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    fontFamily: "var(--font-mono)",
                    color: "var(--color-primary-600)",
                    textDecoration: "none",
                  }}
                >
                  DOI:{groupDetail.doi.slice(0, 30)}
                  <ExternalLink style={{ width: 12, height: 12 }} />
                </a>
              )}
              <span>{groupDetail.item_count} evidence fields</span>
              {groupDetail.avg_confidence != null && (
                <span>
                  {Math.round(groupDetail.avg_confidence * 100)}% confidence
                </span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Main: Bilingual comparison layout */}
      <div className="bev-main-grid">
        {/* Sidebar: controls + navigator */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Category toggles */}
          <div className="edb-card" style={{ borderRadius: 12, padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <h3 style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                margin: 0,
              }}>
                Evidence Layers
              </h3>
              <div style={{ display: "flex", gap: 4 }}>
                <button
                  type="button"
                  onClick={() => toggleAllCategories(true)}
                  className="bev-eye-btn"
                  style={{
                    cursor: "pointer",
                    borderRadius: 4,
                    padding: "2px 6px",
                    fontSize: 10,
                    color: "#9ca3af",
                    border: "none",
                    backgroundColor: "transparent",
                    display: "flex",
                    alignItems: "center",
                  }}
                  title="Show all"
                  aria-label="Show all categories"
                >
                  <Eye style={{ width: 14, height: 14 }} />
                </button>
                <button
                  type="button"
                  onClick={() => toggleAllCategories(false)}
                  className="bev-eye-btn"
                  style={{
                    cursor: "pointer",
                    borderRadius: 4,
                    padding: "2px 6px",
                    fontSize: 10,
                    color: "#9ca3af",
                    border: "none",
                    backgroundColor: "transparent",
                    display: "flex",
                    alignItems: "center",
                  }}
                  title="Hide all"
                  aria-label="Hide all categories"
                >
                  <EyeOff style={{ width: 14, height: 14 }} />
                </button>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {EVIDENCE_CATEGORIES.map((cat) => (
                <CategoryToggle
                  key={cat}
                  category={cat}
                  count={categoryCounts[cat] ?? 0}
                  checked={enabledCategories.has(cat)}
                  onChange={() => toggleCategory(cat)}
                />
              ))}
            </div>
          </div>

          {/* Evidence navigator */}
          <div className="edb-card" style={{ borderRadius: 12, padding: 16 }}>
            <h3 style={{
              fontSize: 12,
              fontWeight: 600,
              color: "#6b7280",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 12,
              margin: 0,
              paddingBottom: 0,
            }}>
              Evidence Fields
            </h3>
            <div className="edb-scroll" style={{ maxHeight: 400, overflowY: "auto" }}>
              <EvidenceNavigator
                items={groupDetail.items}
                selectedId={selectedEvidenceId}
                onSelect={setSelectedEvidenceId}
              />
            </div>
          </div>
        </aside>

        {/* Main: bilingual document readers */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Active evidence card */}
          {selectedEvidenceId && (
            <ActiveEvidenceCard
              item={
                groupDetail.items.find(
                  (i) => i.canonical_evidence_id === selectedEvidenceId,
                ) ?? groupDetail.items[0]
              }
            />
          )}

          {/* Bilingual panels */}
          <div className={`bev-bilingual-grid${hasTranslation ? " bev-bilingual-grid--dual" : ""}`}>
            <DocumentReader
              title="Original Text"
              track="original"
              document={originalDoc ?? { track: "original", paragraphs: [] }}
              accentColor="#3B82F6"
            />
            {hasTranslation && (
              <DocumentReader
                title="Translated Text (Chinese)"
                track="translated"
                document={
                  translatedDoc ?? { track: "translated", paragraphs: [] }
                }
                accentColor="#8B5CF6"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
