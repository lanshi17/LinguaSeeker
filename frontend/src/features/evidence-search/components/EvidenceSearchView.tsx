"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { EvidenceSearchForm } from "./EvidenceSearchForm";
import { EvidenceResultsTable } from "./EvidenceResultsTable";
import { useEvidenceSearch } from "../hooks/useEvidenceSearch";
import { useToastStore } from "@/stores/toastStore";
import type { EvidenceSearchQuery } from "../types/evidenceSearch";

/** Client wrapper for the evidence search page. */
export function EvidenceSearchView() {
  const searchMutation = useEvidenceSearch();
  const addToast = useToastStore((s) => s.addToast);
  const [hasSearched, setHasSearched] = useState(false);

  function handleSearch(query: EvidenceSearchQuery) {
    setHasSearched(true);
    searchMutation.mutate(query, {
      onError: () =>
        addToast({ level: "error", title: "Evidence search failed" }),
    });
  }

  return (
    <div className="space-y-6">
      <ErrorBoundary>
        <Card>
          <EvidenceSearchForm
            onSearch={handleSearch}
            isSearching={searchMutation.isPending}
          />
        </Card>
      </ErrorBoundary>

      {hasSearched && (
        <ErrorBoundary>
          <Card>
            <EvidenceResultsTable
              results={searchMutation.data?.items ?? []}
              total={searchMutation.data?.total}
            />
          </Card>
        </ErrorBoundary>
      )}
    </div>
  );
}
