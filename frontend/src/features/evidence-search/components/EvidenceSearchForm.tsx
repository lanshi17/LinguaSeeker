"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { EvidenceSearchQuery } from "../types/evidenceSearch";

interface EvidenceSearchFormProps {
  filters: EvidenceSearchQuery;
  onUpdateFilter: (key: keyof EvidenceSearchQuery, value: string) => void;
  onSearch: () => void;
  onClear: () => void;
  isSearching?: boolean;
}

export function EvidenceSearchForm({
  filters,
  onUpdateFilter,
  onSearch,
  onClear,
  isSearching,
}: EvidenceSearchFormProps) {
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSearch();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-gray-950">
            Literature filters
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Filter evidence-bearing literature records.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="submit" loading={isSearching}>
            <Search className="mr-2 h-4 w-4" />
            Search
          </Button>
          <Button type="button" variant="ghost" onClick={onClear}>
            <X className="mr-2 h-4 w-4" />
            Clear
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <Input
          label="Gene"
          placeholder="e.g., BRCA1"
          value={filters.gene ?? ""}
          onChange={(e) => onUpdateFilter("gene", e.target.value)}
        />
        <Input
          label="Variant"
          placeholder="e.g., c.5266dupC"
          value={filters.variant ?? ""}
          onChange={(e) => onUpdateFilter("variant", e.target.value)}
        />
        <Input
          label="Disease"
          placeholder="e.g., Breast cancer"
          value={filters.disease ?? ""}
          onChange={(e) => onUpdateFilter("disease", e.target.value)}
        />
        <Input
          label="PMID"
          placeholder="e.g., 12345678"
          value={filters.pmid ?? ""}
          onChange={(e) => onUpdateFilter("pmid", e.target.value)}
        />
      </div>
    </form>
  );
}
