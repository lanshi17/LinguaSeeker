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

interface EvidenceResultsTableProps {
  results: EvidenceSearchResult[];
  total: number;
  page: number;
  pageSize: number;
  isLoading?: boolean;
  onPageChange?: (page: number) => void;
  onRowClick?: (item: LiteratureEvidenceRow) => void;
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

function formatPercent(value?: number | null) {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function formatDate(isoString?: string | null) {
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

function joinedLabel(values: string[]) {
  return values.length > 0 ? values.join(", ") : "\u2014";
}

function literatureTitle(row: LiteratureEvidenceRow) {
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

function TokenList({
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
    <>
      <style>{`
        .edb-results-header {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        @media (min-width: 640px) {
          .edb-results-header {
            flex-direction: row;
            align-items: center;
            justify-content: space-between;
          }
        }
        .edb-mobile-cards { display: block; }
        .edb-desktop-table { display: none; }
        @media (min-width: 768px) {
          .edb-mobile-cards { display: none; }
          .edb-desktop-table { display: block; }
        }
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
        .edb-card {
          width: 100%;
          cursor: pointer;
          border-radius: 12px;
          border: 1px solid #e5e7eb;
          background: #fff;
          padding: 16px;
          text-align: left;
          box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05);
          transition: all 0.15s;
        }
        .edb-card:hover {
          border-color: var(--color-primary-200, #a5f3fc);
          box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }
        .edb-card:focus-visible {
          outline: 2px solid var(--color-primary-500, #06b6d4);
          outline-offset: 0;
        }
        .edb-card:hover .edb-card-title {
          color: var(--color-primary-700, #0e7490);
        }
        .edb-card:hover .edb-card-icon {
          transform: scale(1.05);
        }
        .edb-table-row {
          cursor: pointer;
          transition: all 0.15s;
        }
        .edb-table-row:hover {
          background: linear-gradient(to right, rgba(236, 254, 255, 0.6), transparent);
        }
        .edb-table-row:focus-visible {
          outline: 2px solid var(--color-primary-500, #06b6d4);
          outline-offset: -2px;
        }
        .edb-table-row:hover .edb-row-title {
          color: var(--color-primary-700, #0e7490);
        }
        .edb-table-row:hover .edb-row-icon {
          transform: scale(1.05);
        }
      `}</style>
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
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      <TokenList values={row.genes} tone="primary" />
                      <TokenList values={row.variants} tone="success" />
                    </div>
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <p
                      className="edb-line-clamp-3"
                      style={{ color: "#374151" }}
                      title={joinedLabel(row.diseases)}
                    >
                      {joinedLabel(row.diseases)}
                    </p>
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <TokenList values={row.classifications} tone="amber" />
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#6b7280" }}>
                      <Calendar style={{ width: 14, height: 14, color: "#9ca3af" }} />
                      {formatDate(row.createdAt)}
                    </div>
                  </td>
                  <td style={{ padding: "16px", verticalAlign: "top" }}>
                    <Badge variant={STATUS_VARIANT[row.reviewStatus] ?? "info"}>
                      {row.reviewStatus}
                    </Badge>
                    <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "#6b7280" }}>
                      <BarChart3 style={{ width: 12, height: 12 }} />
                      {formatPercent(row.avgConfidence)}
                    </div>
                  </td>
                  <td style={{ padding: "16px", textAlign: "right", verticalAlign: "top" }}>
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
