import { STATUS_VARIANT } from "@/lib/constants/statusVariant";
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Layers3,
  Search,
  Database,
  BarChart3,
  Calendar,
} from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { Badge } from "@/components/ui/Badge";
import type { EvidenceSearchResult } from "../types/evidenceSearch";
import { EvidenceTableSkeleton } from "./EvidenceTableSkeleton";
import {
  buildLiteratureRows,
  type LiteratureEvidenceRow,
} from "../utils/literatureRows";
import {
  formatDate,
  joinedLabel,
  literatureTitle,
  TokenList,
  StatBadge,
  LiteratureCell,
  EvidenceFocusCell,
  DiseaseCell,
  ClassificationCell,
  CreatedCell,
  ReviewCell,
  FieldsCell,
} from "./evidenceTableColumns";

interface EvidenceResultsTableProps {
  results: EvidenceSearchResult[];
  total: number;
  page: number;
  pageSize: number;
  isLoading?: boolean;
  onPageChange?: (page: number) => void;
  onRowClick?: (item: LiteratureEvidenceRow) => void;
}

export function EvidenceResultsTable({
  results,
  total,
  page,
  pageSize,
  isLoading,
  onPageChange,
  onRowClick,
}: EvidenceResultsTableProps) {
  const rows = buildLiteratureRows(results);
  const { t } = useI18n();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  if (isLoading) {
    return <EvidenceTableSkeleton />;
  }

  if (rows.length === 0) {
    return (
      <div
        style={{
          position: "relative",
          overflow: "hidden",
          borderRadius: 12,
          border: "1px dashed var(--color-text-muted)",
          background: "linear-gradient(to bottom right, var(--color-bg), var(--color-surface))",
          padding: "64px 24px",
          textAlign: "center",
        }}
      >
        {/* Decorative background */}
        <div style={{ position: "absolute", inset: 0, opacity: 0.03 }}>
          <svg
            style={{ width: "100%", height: "100%" }}
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            <defs>
              <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
                <path d="M 10 0 L 0 0 0 10" fill="none" stroke="currentColor" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100" height="100" fill="url(#grid)" />
          </svg>
        </div>
        <div style={{ position: "relative" }}>
          <div
            style={{
              margin: "0 auto",
              display: "flex",
              height: 64,
              width: 64,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 16,
              background: "linear-gradient(to bottom right, var(--color-primary-100), var(--color-primary-50))",
              boxShadow: "inset 0 2px 4px 0 rgba(0,0,0,0.05)",
            }}
          >
            <Search style={{ width: 32, height: 32, color: "var(--color-primary-500, var(--color-primary-500))" }} />
          </div>
          <p style={{ marginTop: 20, fontSize: 16, fontWeight: 600, color: "var(--color-text)" }}>
            {t("evidence.results.empty")}
          </p>
          <p style={{ marginTop: 8, maxWidth: 384, margin: "8px auto 0", fontSize: 14, color: "var(--color-text-secondary)" }}>
            {t("evidence.results.guidance")}
          </p>
        </div>
      </div>
    );
  }

  return (
      <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Results header with stats and pagination */}
        <div
          className="edb-results-header"
          style={{
            borderRadius: 12,
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            padding: "16px 20px",
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                display: "flex",
                height: 40,
                width: 40,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 8,
                backgroundColor: "var(--color-primary-50, var(--color-primary-50))",
              }}
            >
              <Database style={{ width: 20, height: 20, color: "var(--color-primary-600, var(--color-primary-600))" }} />
            </div>
            <div>
              <p style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                {rows.length} {t("evidence.results.rows")}
              </p>
              <p style={{ marginTop: 2, fontSize: 12, color: "var(--color-text-secondary)" }}>
                {total} {t("evidence.results.groups")}
                <span style={{ margin: "0 6px", color: "var(--color-text-muted)" }}>·</span>
                {t("evidence.results.showing", { from: String(startItem), to: String(endItem) })}
              </p>
            </div>
          </div>

          {/* Modern pagination */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              borderRadius: 8,
              backgroundColor: "var(--color-bg)",
              padding: 4,
            }}
          >
            <button
              onClick={() => onPageChange?.(page - 1)}
              disabled={page <= 1}
              aria-label={t("evidence.results.prevPage")}
            >
              <ChevronLeft style={{ width: 16, height: 16 }} />
            </button>
            <div
              style={{
                display: "flex",
                height: 32,
                minWidth: "4rem",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 6,
                backgroundColor: "var(--color-surface)",
                padding: "0 12px",
                boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
              }}
            >
              <span style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>
                {page}
              </span>
              <span style={{ margin: "0 4px", color: "var(--color-text-muted)" }}>/</span>
              <span style={{ fontSize: 14, color: "var(--color-text-secondary)" }}>
                {totalPages}
              </span>
            </div>
            <button
              onClick={() => onPageChange?.(page + 1)}
              disabled={page >= totalPages}
              aria-label={t("evidence.results.nextPage")}
            >
              <ChevronRight style={{ width: 16, height: 16 }} />
            </button>
          </div>
        </div>

        {/* Mobile cards */}
        <div className="edb-mobile-cards" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {rows.map((row, index) => (
            <button
              key={row.documentId}
              type="button"
              onClick={() => onRowClick?.(row)}
              className="edb-card"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <span
                  className="edb-card-icon"
                  style={{
                    display: "flex",
                    height: 44,
                    width: 44,
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
                  <FileText style={{ width: 20, height: 20 }} />
                </span>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <p
                    className="edb-card-title edb-line-clamp-2"
                    style={{ fontSize: 14, fontWeight: 600, lineHeight: "20px", color: "var(--color-text)", transition: "color 0.15s" }}
                  >
                    {literatureTitle(row, t)}
                  </p>
                  <p
                    style={{
                      marginTop: 4,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      fontFamily: "monospace",
                      fontSize: 12,
                      color: "var(--color-text-muted)",
                    }}
                  >
                    {row.documentId.slice(0, 8)}...
                  </p>
                </div>
                <Badge variant={STATUS_VARIANT[row.reviewStatus as keyof typeof STATUS_VARIANT] ?? "info"}>
                  {row.reviewStatus}
                </Badge>
              </div>
              <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "var(--color-text-secondary)" }}>
                  <span style={{ borderRadius: 4, backgroundColor: "var(--color-bg-muted)", padding: "2px 6px" }}>
                    PMID {row.pmid ?? "\u2014"}
                  </span>
                  <span style={{ borderRadius: 4, backgroundColor: "var(--color-bg-muted)", padding: "2px 6px" }}>
                    DOI {row.doi ?? "\u2014"}
                  </span>
                </div>
                <TokenList values={row.genes} tone="primary" />
                <TokenList values={row.variants} tone="success" />
                <p className="edb-line-clamp-2" style={{ fontSize: 14, color: "var(--color-text-strong)" }}>
                  {joinedLabel(row.diseases)}
                </p>
              </div>
              <div
                style={{
                  marginTop: 16,
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                  borderTop: "1px solid var(--color-bg-muted)",
                  paddingTop: 12,
                }}
              >
                <StatBadge icon={Layers3} value={row.groupCount} label="groups" />
                <StatBadge icon={BarChart3} value={row.fieldCount} label="fields" />
                <StatBadge icon={Calendar} value={formatDate(row.createdAt)} label="" />
              </div>
            </button>
          ))}
        </div>

        {/* Desktop table */}
        <div
          className="edb-desktop-table"
          style={{
            overflow: "hidden",
            borderRadius: 12,
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
          }}
        >
          <table style={{ width: "100%", tableLayout: "fixed", fontSize: 14, borderCollapse: "collapse" }}>
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid var(--color-border)",
                  background: "linear-gradient(to right, var(--color-bg), var(--color-bg), var(--color-subtle-bg))",
                }}
              >
                <th style={{ width: "20%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-secondary)" }}>
                  {t("evidence.results.colLiterature")}
                </th>
                <th style={{ width: "18%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-secondary)" }}>
                  {t("evidence.results.colFocus")}
                </th>
                <th style={{ width: "16%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-secondary)" }}>
                  {t("evidence.results.colDisease")}
                </th>
                <th style={{ width: "14%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-secondary)" }}>
                  {t("evidence.results.colClass")}
                </th>
                <th style={{ width: "10%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-secondary)" }}>
                  {t("evidence.results.colCreated")}
                </th>
                <th style={{ width: "10%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-secondary)" }}>
                  {t("evidence.results.colReview")}
                </th>
                <th style={{ width: "8%", padding: "14px 16px", textAlign: "right", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-secondary)" }}>
                  {t("evidence.results.colFields")}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.documentId}
                  role={onRowClick ? "link" : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-label={`${t("evidence.results.openLit")} ${row.title ?? row.pmid ?? row.documentId}`}
                  onClick={() => onRowClick?.(row)}
                  onKeyDown={(e) => {
                    if (onRowClick && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      onRowClick(row);
                    }
                  }}
                  className="edb-table-row"
                  style={{ borderBottom: "1px solid var(--color-bg-muted)" }}
                >
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <LiteratureCell row={row} />
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <EvidenceFocusCell row={row} />
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <DiseaseCell row={row} />
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <ClassificationCell row={row} />
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <CreatedCell row={row} />
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <ReviewCell row={row} />
                  </td>
                  <td style={{ padding: "16px", textAlign: "right", verticalAlign: "top" }}>
                    <FieldsCell row={row} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
  );
}
