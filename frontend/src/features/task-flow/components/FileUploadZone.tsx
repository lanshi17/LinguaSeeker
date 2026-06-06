"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils/cn";

interface FileUploadZoneProps {
  onFilesSelected: (files: File[]) => void;
  maxFiles?: number;
  accept?: string;
  disabled?: boolean;
}

export function FileUploadZone({
  onFilesSelected,
  maxFiles = 10,
  accept = ".pdf,.docx",
  disabled,
}: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;

      const files = Array.from(e.dataTransfer.files).slice(0, maxFiles);
      onFilesSelected(files);
    },
    [disabled, maxFiles, onFilesSelected],
  );

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []).slice(0, maxFiles);
    onFilesSelected(files);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
        isDragging
          ? "border-primary-400 bg-primary-50"
          : "border-gray-300 bg-gray-50",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <p className="text-sm text-gray-600">
        Drag & drop files here, or{" "}
        <label className="cursor-pointer font-medium text-primary-600 hover:underline">
          browse
          <input
            type="file"
            accept={accept}
            multiple
            onChange={handleChange}
            disabled={disabled}
            className="hidden"
          />
        </label>
      </p>
      <p className="mt-1 text-xs text-gray-400">
        Max {maxFiles} files, 10MB each (PDF, DOCX)
      </p>
    </div>
  );
}
