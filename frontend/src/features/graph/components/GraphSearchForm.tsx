"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { GraphSearchRequest } from "../types/graph";

interface GraphSearchFormProps {
  onSearch: (params: GraphSearchRequest) => void;
  isSearching?: boolean;
}

export function GraphSearchForm({ onSearch, isSearching }: GraphSearchFormProps) {
  const [form, setForm] = useState<GraphSearchRequest>({});

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
        onChange={(e) => setForm({ ...form, variant: e.target.value || undefined })}
      />
      <Input
        label="Protein Change"
        placeholder="e.g., p.Gln1756Profs"
        value={form.protein_change ?? ""}
        onChange={(e) => setForm({ ...form, protein_change: e.target.value || undefined })}
      />
      <Input
        label="Disease"
        placeholder="e.g., Breast cancer"
        value={form.disease ?? ""}
        onChange={(e) => setForm({ ...form, disease: e.target.value || undefined })}
      />
      <div className="md:col-span-2">
        <Button type="submit" loading={isSearching}>
          Search Graph
        </Button>
      </div>
    </form>
  );
}
