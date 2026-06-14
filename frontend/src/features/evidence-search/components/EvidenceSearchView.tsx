"use client";

import { useRouter } from "next/navigation";
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
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <EvidenceSearchForm
            filters={filters}
            onUpdateFilter={updateFilter}
            onSearch={applyFilters}
            onClear={clearFilters}
            isSearching={isFetching}
          />
        </div>
      </ErrorBoundary>

      <ErrorBoundary>
        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-6 py-10 text-center">
            <p className="text-sm font-medium text-red-700">
              Failed to load evidence
            </p>
            <p className="mt-1 text-xs text-red-600">
              {error.message}
            </p>
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
