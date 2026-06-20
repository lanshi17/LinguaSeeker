
import { Search, X, Dna, FlaskConical, Stethoscope, Hash } from "lucide-react";
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
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Header with accent */}
      <div className="relative overflow-hidden rounded-lg bg-gradient-to-r from-primary-50 via-primary-50/50 to-transparent px-5 py-4">
        <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-primary-400 to-primary-600" />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-100 text-primary-700">
              <Search className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-950">
                Literature Evidence Search
              </h2>
              <p className="mt-0.5 text-sm text-gray-600">
                Search by gene, variant, disease, or publication identifier
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button type="submit" loading={isSearching} className="shadow-sm">
              <Search className="mr-2 h-4 w-4" />
              Search
            </Button>
            <Button type="button" variant="ghost" onClick={onClear}>
              <X className="mr-2 h-4 w-4" />
              Clear
            </Button>
          </div>
        </div>
      </div>

      {/* Input fields with icons */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="group relative">
          <div className="pointer-events-none absolute left-3 top-[38px] z-10 text-gray-400 transition-colors group-focus-within:text-primary-500">
            <Dna className="h-4 w-4" />
          </div>
          <Input
            label="Gene"
            placeholder="e.g., BRCA1"
            value={filters.gene ?? ""}
            onChange={(e) => onUpdateFilter("gene", e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="group relative">
          <div className="pointer-events-none absolute left-3 top-[38px] z-10 text-gray-400 transition-colors group-focus-within:text-primary-500">
            <FlaskConical className="h-4 w-4" />
          </div>
          <Input
            label="Variant"
            placeholder="e.g., c.5266dupC"
            value={filters.variant ?? ""}
            onChange={(e) => onUpdateFilter("variant", e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="group relative">
          <div className="pointer-events-none absolute left-3 top-[38px] z-10 text-gray-400 transition-colors group-focus-within:text-primary-500">
            <Stethoscope className="h-4 w-4" />
          </div>
          <Input
            label="Disease"
            placeholder="e.g., Breast cancer"
            value={filters.disease ?? ""}
            onChange={(e) => onUpdateFilter("disease", e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="group relative">
          <div className="pointer-events-none absolute left-3 top-[38px] z-10 text-gray-400 transition-colors group-focus-within:text-primary-500">
            <Hash className="h-4 w-4" />
          </div>
          <Input
            label="PMID"
            placeholder="e.g., 12345678"
            value={filters.pmid ?? ""}
            onChange={(e) => onUpdateFilter("pmid", e.target.value)}
            className="pl-9"
          />
        </div>
      </div>
    </form>
  );
}
