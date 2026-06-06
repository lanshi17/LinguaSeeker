"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { usePipelineRun } from "../hooks/usePipelineRun";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { useToastStore } from "@/stores/toastStore";
import type { PipelineRunRequest } from "../types/pipeline";

export function PipelineSubmitForm() {
  const router = useRouter();
  const addToast = useToastStore((s) => s.addToast);
  const { mutateAsync: startRun, isPending } = usePipelineRun();

  const [sourceType, setSourceType] = useState<"local" | "online">("online");
  const [query, setQuery] = useState("");
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [filename, setFilename] = useState<string>("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const body: PipelineRunRequest = {
      source_type: sourceType,
      mode: "full",
    };

    if (sourceType === "online") {
      body.query = query;
    } else if (fileContent) {
      body.file_content = fileContent;
      body.filename = filename;
    }

    try {
      const result = await startRun(body);
      addToast({ level: "success", title: "Pipeline started" });
      router.push(`/pipeline/${result.processing_run_id}`);
    } catch {
      addToast({ level: "error", title: "Failed to start pipeline" });
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setFilename(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(",")[1];
      setFileContent(base64);
    };
    reader.readAsDataURL(file);
  }

  return (
    <Card>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Select
          label="Source Type"
          value={sourceType}
          onChange={(e) => setSourceType(e.target.value as "local" | "online")}
          options={[
            { label: "Online Search", value: "online" },
            { label: "Local File Upload", value: "local" },
          ]}
        />

        {sourceType === "online" ? (
          <Input
            label="Search Query"
            placeholder="e.g., BRCA1 pathogenic variant breast cancer"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            required
          />
        ) : (
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Upload PDF
            </label>
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-primary-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-primary-700 hover:file:bg-primary-100"
            />
            {filename && (
              <p className="mt-1 text-xs text-gray-500">{filename}</p>
            )}
          </div>
        )}

        <Button
          type="submit"
          loading={isPending}
          disabled={sourceType === "online" ? !query : !fileContent}
        >
          Start Pipeline
        </Button>
      </form>
    </Card>
  );
}
