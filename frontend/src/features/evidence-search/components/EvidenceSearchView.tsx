"use client";

import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { EvidenceSearchForm } from "./EvidenceSearchForm";
import { EvidenceResultsTable } from "./EvidenceResultsTable";
import { useEvidenceSearch } from "../hooks/useEvidenceSearch";

export function EvidenceSearchView() {
  const router = useRouter();
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
    <div className="space-y-6">
      <ErrorBoundary>
        <Card className="border-primary-100 bg-white shadow-sm">
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
          <Card className="py-10 text-center">
            <p className="text-sm text-red-600">
              Failed to load evidence: {error.message}
            </p>
          </Card>
        ) : (
          <EvidenceResultsTable
            results={results}
            total={total}
            page={page}
            pageSize={pageSize}
            isLoading={isLoading}
            onPageChange={setPage}
            onRowClick={(item) => {
              router.push(
                `/evidence/detail?groupId=${encodeURIComponent(item.representativeGroupId)}`,
              );
            }}
          />
        )}
      </ErrorBoundary>
    </div>
  );
}
