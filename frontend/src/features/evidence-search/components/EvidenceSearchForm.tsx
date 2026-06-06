"use client";

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
    <form onSubmit={handleSubmit} className="space-y-3">
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
      <div className="flex items-center gap-2">
        <Button type="submit" loading={isSearching}>
          Search
        </Button>
        <Button type="button" variant="ghost" onClick={onClear}>
          Clear
        </Button>
      </div>
    </form>
  );
}
