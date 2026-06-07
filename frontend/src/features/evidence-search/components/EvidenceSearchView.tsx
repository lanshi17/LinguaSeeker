"use client";

import { Card } from "@/components/ui/Card";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { EvidenceSearchForm } from "./EvidenceSearchForm";
import { EvidenceResultsTable } from "./EvidenceResultsTable";
import { useEvidenceSearch } from "../hooks/useEvidenceSearch";

export function EvidenceSearchView() {
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
        <Card>
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
          />
        )}
      </ErrorBoundary>
    </div>
  );
}
