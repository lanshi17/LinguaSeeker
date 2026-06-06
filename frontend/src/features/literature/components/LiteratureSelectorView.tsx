"use client";

import { LiteratureCandidateList } from "./LiteratureCandidateList";
import { SelectionToolbar } from "./SelectionToolbar";
import { useCandidateSearch } from "../hooks/useCandidateSearch";
import { useCandidateSelection } from "../hooks/useCandidateSelection";
import { useToastStore } from "@/stores/toastStore";
import { Button } from "@/components/ui/Button";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

/** Client wrapper for the literature candidate selection page. */
export function LiteratureSelectorView() {
  const searchMutation = useCandidateSearch();
  const { selectedIds, selectedCount, toggle, clear, isAtLimit } =
    useCandidateSelection();
  const addToast = useToastStore((s) => s.addToast);

  function handleSearch() {
    searchMutation.mutate(
      { target: "ACMG evidence", candidate_limit: 20 },
      {
        onError: () =>
          addToast({ level: "error", title: "Literature search failed" }),
      },
    );
  }

  function handleSubmit() {
    addToast({
      level: "success",
      title: `${selectedCount} paper(s) selected`,
    });
    clear();
  }

  return (
    <div className="space-y-4">
      <ErrorBoundary>
        <div className="flex items-center gap-3">
          <Button onClick={handleSearch} loading={searchMutation.isPending}>
            Search Literature
          </Button>
          {searchMutation.data && (
            <span className="text-sm text-gray-500">
              {searchMutation.data.candidates.length} candidates found
            </span>
          )}
        </div>
      </ErrorBoundary>

      {searchMutation.data && (
        <ErrorBoundary>
          <LiteratureCandidateList
            candidates={searchMutation.data.candidates}
            selectedIds={selectedIds}
            onToggle={toggle}
            isLoading={searchMutation.isPending}
            isAtLimit={isAtLimit}
          />
          <SelectionToolbar
            selectedCount={selectedCount}
            onSubmit={handleSubmit}
          />
        </ErrorBoundary>
      )}
    </div>
  );
}
