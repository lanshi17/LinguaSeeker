"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";

interface WebCrawlFormProps {
  onSubmit: (urls: string[]) => void;
  isSubmitting?: boolean;
}

export function WebCrawlForm({ onSubmit, isSubmitting }: WebCrawlFormProps) {
  const [urlText, setUrlText] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const urls = urlText
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length > 0) onSubmit(urls);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">
        URLs (one per line)
      </label>
      <textarea
        value={urlText}
        onChange={(e) => setUrlText(e.target.value)}
        rows={5}
        placeholder="https://pubmed.ncbi.nlm.nih.gov/12345678&#10;https://doi.org/10.1000/xyz"
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
      />
      <Button type="submit" loading={isSubmitting} disabled={!urlText.trim()}>
        Submit URLs
      </Button>
    </form>
  );
}
