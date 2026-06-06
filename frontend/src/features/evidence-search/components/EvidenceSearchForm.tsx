"use client";

import { useState } from "react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { EvidenceSearchQuery } from "../types/evidenceSearch";

interface EvidenceSearchFormProps {
  onSearch: (query: EvidenceSearchQuery) => void;
  isSearching?: boolean;
}

export function EvidenceSearchForm({
  onSearch,
  isSearching,
}: EvidenceSearchFormProps) {
  const [form, setForm] = useState<EvidenceSearchQuery>({});

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSearch(form);
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-2">
      <Input
        label="Gene"
        placeholder="e.g., BRCA1"
        value={form.gene ?? ""}
        onChange={(e) => setForm({ ...form, gene: e.target.value || undefined })}
      />
      <Input
        label="Variant"
        placeholder="e.g., c.5266dupC"
        value={form.variant ?? ""}
        onChange={(e) =>
          setForm({ ...form, variant: e.target.value || undefined })
        }
      />
      <Input
        label="Disease"
        placeholder="e.g., Breast cancer"
        value={form.disease ?? ""}
        onChange={(e) =>
          setForm({ ...form, disease: e.target.value || undefined })
        }
      />
      <Input
        label="PMID"
        placeholder="e.g., 12345678"
        value={form.pmid ?? ""}
        onChange={(e) => setForm({ ...form, pmid: e.target.value || undefined })}
      />
      <div className="md:col-span-2">
        <Button type="submit" loading={isSearching}>
          Search Evidence
        </Button>
      </div>
    </form>
  );
}
