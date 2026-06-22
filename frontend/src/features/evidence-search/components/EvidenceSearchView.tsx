import { useNavigate } from "react-router-dom";
import { Card, Typography } from "antd";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { EvidenceSearchForm } from "./EvidenceSearchForm";
import { EvidenceResultsTable } from "./EvidenceResultsTable";
import { useEvidenceSearch } from "../hooks/useEvidenceSearch";

export function EvidenceSearchView() {
  const navigate = useNavigate();
  const {
    results,
    total,
    page,
    pageSize,
    isLoading,
    isFetching,
    error,
    filters,
    updateFilter,
    applyFilters,
    clearFilters,
    setPage,
  } = useEvidenceSearch();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <ErrorBoundary>
        <Card styles={{ body: { padding: 20 } }}>
          <EvidenceSearchForm
            filters={filters}
            onUpdateFilter={updateFilter}
            onSearch={applyFilters}
            onClear={clearFilters}
            isSearching={isFetching}
          />
        </Card>
      </ErrorBoundary>

      <ErrorBoundary>
        {error ? (
          <div style={{
            borderRadius: 12,
            border: "1px solid #fecaca",
            backgroundColor: "#fef2f2",
            padding: "40px 24px",
            textAlign: "center",
          }}>
            <Typography.Text strong style={{ color: "#b91c1c", fontSize: 14 }}>
              Failed to load evidence
            </Typography.Text>
            <br />
            <Typography.Text type="secondary" style={{ color: "#dc2626", fontSize: 12 }}>
              {error.message}
            </Typography.Text>
          </div>
        ) : (
          <EvidenceResultsTable
            results={results}
            total={total}
            page={page}
            pageSize={pageSize}
            isLoading={isLoading}
            onPageChange={setPage}
            onRowClick={(item) => {
              navigate(
                `/evidence/detail?groupId=${encodeURIComponent(item.representativeGroupId)}`,
              );
            }}
          />
        )}
      </ErrorBoundary>
    </div>
  );
}
