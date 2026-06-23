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
import { Badge } from "@/components/ui/Badge";
import type { EvidenceSearchResult } from "../types/evidenceSearch";
import { EvidenceTableSkeleton } from "./EvidenceTableSkeleton";
import {
  buildLiteratureRows,
  type LiteratureEvidenceRow,
} from "../utils/literatureRows";
import {
  STATUS_VARIANT,
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
          border: "1px dashed #d1d5db",
          background: "linear-gradient(to bottom right, #f9fafb, #fff)",
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
              background: "linear-gradient(to bottom right, var(--color-primary-100, #cffafe), var(--color-primary-50, #ecfeff))",
              boxShadow: "inset 0 2px 4px 0 rgba(0,0,0,0.05)",
            }}
          >
            <Search style={{ width: 32, height: 32, color: "var(--color-primary-500, #06b6d4)" }} />
          </div>
          <p style={{ marginTop: 20, fontSize: 16, fontWeight: 600, color: "#111827" }}>
            No literature matched this search
          </p>
          <p style={{ marginTop: 8, maxWidth: 384, margin: "8px auto 0", fontSize: 14, color: "#6b7280" }}>
            Try adjusting the gene, variant, disease, or PMID filters to broaden your search criteria.
          </p>
        </div>
      </div>
    );
  }

  const paginationBtnStyle: React.CSSProperties = {
    display: "flex",
    height: 32,
    width: 32,
    cursor: "pointer",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 6,
    color: "#4b5563",
    border: "none",
    background: "transparent",
    transition: "all 0.15s",
  };

  const paginationBtnDisabledStyle: React.CSSProperties = {
    ...paginationBtnStyle,
    cursor: "not-allowed",
    opacity: 0.3,
  };

  return (
      <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Results header with stats and pagination */}
        <div
          className="edb-results-header"
          style={{
            borderRadius: 12,
            border: "1px solid #e5e7eb",
            backgroundColor: "#fff",
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
                backgroundColor: "var(--color-primary-50, #ecfeff)",
              }}
            >
              <Database style={{ width: 20, height: 20, color: "var(--color-primary-600, #0891b2)" }} />
            </div>
            <div>
              <p style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
                {rows.length} literature row{rows.length !== 1 ? "s" : ""}
              </p>
              <p style={{ marginTop: 2, fontSize: 12, color: "#6b7280" }}>
                {total} evidence group{total !== 1 ? "s" : ""} total
                <span style={{ margin: "0 6px", color: "#d1d5db" }}>·</span>
                Showing {startItem}&ndash;{endItem}
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
              backgroundColor: "#f9fafb",
              padding: 4,
            }}
          >
            <button
              onClick={() => onPageChange?.(page - 1)}
              disabled={page <= 1}
              style={page <= 1 ? paginationBtnDisabledStyle : paginationBtnStyle}
              aria-label="Previous page"
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
                backgroundColor: "#fff",
                padding: "0 12px",
                boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
              }}
            >
              <span style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>
                {page}
              </span>
              <span style={{ margin: "0 4px", color: "#9ca3af" }}>/</span>
              <span style={{ fontSize: 14, color: "#6b7280" }}>
                {totalPages}
              </span>
            </div>
            <button
              onClick={() => onPageChange?.(page + 1)}
              disabled={page >= totalPages}
              style={page >= totalPages ? paginationBtnDisabledStyle : paginationBtnStyle}
              aria-label="Next page"
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
                    background: "linear-gradient(to bottom right, var(--color-primary-100, #cffafe), var(--color-primary-50, #ecfeff))",
                    color: "var(--color-primary-700, #0e7490)",
                    boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
                    transition: "transform 0.15s",
                  }}
                >
                  <FileText style={{ width: 20, height: 20 }} />
                </span>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <p
                    className="edb-card-title edb-line-clamp-2"
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
                </div>
                <Badge variant={STATUS_VARIANT[row.reviewStatus] ?? "info"}>
                  {row.reviewStatus}
                </Badge>
              </div>
              <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#6b7280" }}>
                  <span style={{ borderRadius: 4, backgroundColor: "#f3f4f6", padding: "2px 6px" }}>
                    PMID {row.pmid ?? "\u2014"}
                  </span>
                  <span style={{ borderRadius: 4, backgroundColor: "#f3f4f6", padding: "2px 6px" }}>
                    DOI {row.doi ?? "\u2014"}
                  </span>
                </div>
                <TokenList values={row.genes} tone="primary" />
                <TokenList values={row.variants} tone="success" />
                <p className="edb-line-clamp-2" style={{ fontSize: 14, color: "#374151" }}>
                  {joinedLabel(row.diseases)}
                </p>
              </div>
              <div
                style={{
                  marginTop: 16,
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                  borderTop: "1px solid #f3f4f6",
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
            border: "1px solid #e5e7eb",
            backgroundColor: "#fff",
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
          }}
        >
          <table style={{ width: "100%", tableLayout: "fixed", fontSize: 14, borderCollapse: "collapse" }}>
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid #e5e7eb",
                  background: "linear-gradient(to right, #f9fafb, #f9fafb, rgba(249,250,251,0.5))",
                }}
              >
                <th style={{ width: "20%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "#6b7280" }}>
                  Literature
                </th>
                <th style={{ width: "18%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "#6b7280" }}>
                  Evidence Focus
                </th>
                <th style={{ width: "16%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "#6b7280" }}>
                  Disease
                </th>
                <th style={{ width: "14%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "#6b7280" }}>
                  Classification
                </th>
                <th style={{ width: "10%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "#6b7280" }}>
                  Created
                </th>
                <th style={{ width: "10%", padding: "14px 16px", textAlign: "left", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "#6b7280" }}>
                  Review
                </th>
                <th style={{ width: "8%", padding: "14px 16px", textAlign: "right", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "#6b7280" }}>
                  Fields
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.documentId}
                  role={onRowClick ? "link" : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-label={`Open literature evidence ${row.title ?? row.pmid ?? row.documentId}`}
                  onClick={() => onRowClick?.(row)}
                  onKeyDown={(e) => {
                    if (onRowClick && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      onRowClick(row);
                    }
                  }}
                  className="edb-table-row"
                  style={{ borderBottom: "1px solid #f3f4f6" }}
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
