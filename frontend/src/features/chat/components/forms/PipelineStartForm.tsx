"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Upload, Search } from "lucide-react";

interface PipelineStartFormProps {
  onSubmit: (data: PipelineFormData) => void;
  isSubmitting?: boolean;
}

export interface PipelineFormData {
  sourceType: "online" | "local";
  query?: string;
  file?: File;
}

/**
 * Inline form for starting a pipeline, rendered inside a chat bubble.
 *
 * Two modes:
 * - Online: search by query/PMID/DOI
 * - Local: upload a PDF file
 */
export function PipelineStartForm({
  onSubmit,
  isSubmitting,
}: PipelineStartFormProps) {
  const [sourceType, setSourceType] = useState<"online" | "local">("online");
  const [query, setQuery] = useState("");
  const [file, setFile] = useState<File | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      sourceType,
      query: sourceType === "online" ? query : undefined,
      file: sourceType === "local" ? file ?? undefined : undefined,
    });
  }

  const canSubmit =
    sourceType === "online" ? query.trim().length > 0 : file !== null;

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Select
        label="Source Type"
        value={sourceType}
        onChange={(e) => setSourceType(e.target.value as "online" | "local")}
        options={[
          { label: "Online Search (PMID / DOI / Query)", value: "online" },
          { label: "Upload PDF Document", value: "local" },
        ]}
      />

      {sourceType === "online" ? (
        <Input
          label="Search Query"
          placeholder="e.g., BRCA1 pathogenic variant OR PMID: 12345678"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      ) : (
        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-700">
            PDF Document
          </label>
          <label
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 transition-colors ${
              file
                ? "border-primary-300 bg-primary-50"
                : "border-gray-300 hover:border-primary-300 hover:bg-gray-50"
            }`}
          >
            <Upload className="mb-1 h-5 w-5 text-gray-400" />
            <span className="text-sm text-gray-600">
              {file ? file.name : "Click to select PDF"}
            </span>
            <span className="mt-0.5 text-xs text-gray-400">Max 50MB</span>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
          </label>
        </div>
      )}

      <Button
        type="submit"
        loading={isSubmitting}
        disabled={!canSubmit}
        className="w-full"
      >
        {sourceType === "online" ? (
          <>
            <Search className="mr-1.5 h-4 w-4" />
            Start Pipeline
          </>
        ) : (
          <>
            <Upload className="mr-1.5 h-4 w-4" />
            Upload & Start
          </>
        )}
      </Button>
    </form>
  );
}
