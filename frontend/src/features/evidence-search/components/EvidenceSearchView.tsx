"use client";

import { Card } from "@/components/ui/Card";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { EvidenceSearchForm } from "./EvidenceSearchForm";
import { EvidenceResultsTable } from "./EvidenceResultsTable";
import { useEvidenceSearch } from "../hooks/useEvidenceSearch";

/**
 * Evidence search page — traditional database query pattern.
 *
 * Auto-loads all evidence on mount. User filters via form fields.
 * Results sorted by PMID (literature ID).
 */
export function EvidenceSearchView() {
  const {
    results,
    total,
    isLoading,
    isFetching,
    error,
    filters,
    updateFilter,
    applyFilters,
    clearFilters,
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
              Failed to load evidence. The backend search endpoint may not be
              available yet.
            </p>
          </Card>
        ) : (
          <EvidenceResultsTable
            results={results}
            total={total}
            isLoading={isLoading}
          />
        )}
      </ErrorBoundary>
    </div>
  );
}
