"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { FileUploadZone } from "./FileUploadZone";
import { WebCrawlForm } from "./WebCrawlForm";
import { useToastStore } from "@/stores/toastStore";
import type { TaskFlowEntryMode } from "../types/taskFlow";

/** Client wrapper for the task upload/crawl page. */
export function TaskUploadView() {
  const [entryMode, setEntryMode] = useState<TaskFlowEntryMode>("local");
  const [files, setFiles] = useState<File[]>([]);
  const addToast = useToastStore((s) => s.addToast);

  function handleFilesSelected(selected: File[]) {
    setFiles(selected);
    addToast({
      level: "info",
      title: `${selected.length} file(s) selected`,
    });
  }

  function handleCrawlSubmit(urls: string[]) {
    addToast({
      level: "info",
      title: `${urls.length} URL(s) submitted`,
      message: "Processing will begin shortly.",
    });
  }

  return (
    <div className="space-y-6">
      <ErrorBoundary>
        <Select
          label="Entry Mode"
          value={entryMode}
          onChange={(e) => setEntryMode(e.target.value as TaskFlowEntryMode)}
          options={[
            { label: "Upload Documents", value: "local" },
            { label: "Web Crawl", value: "online" },
          ]}
        />
      </ErrorBoundary>

      {entryMode === "local" ? (
        <ErrorBoundary>
          <Card>
            <FileUploadZone onFilesSelected={handleFilesSelected} />
            {files.length > 0 && (
              <div className="mt-4">
                <p className="text-sm text-gray-600">
                  {files.length} file(s) ready:
                </p>
                <ul className="mt-1 list-inside list-disc text-sm text-gray-500">
                  {files.map((f) => (
                    <li key={f.name}>
                      {f.name} ({(f.size / 1024 / 1024).toFixed(1)}MB)
                    </li>
                  ))}
                </ul>
                <Button className="mt-4">Submit Files</Button>
              </div>
            )}
          </Card>
        </ErrorBoundary>
      ) : (
        <ErrorBoundary>
          <Card>
            <WebCrawlForm onSubmit={handleCrawlSubmit} />
          </Card>
        </ErrorBoundary>
      )}
    </div>
  );
}
