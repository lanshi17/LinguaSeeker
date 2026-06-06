"use client";

import { useState } from "react";
import { BilingualReadingPane } from "./BilingualReadingPane";
import { EvidenceJudgmentPane } from "./EvidenceJudgmentPane";
import { useDocumentData } from "../hooks/useDocumentData";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils/cn";

interface DocumentViewerProps {
  documentId: string;
}

type TabKey = "reading" | "judgment";

export function DocumentViewer({ documentId }: DocumentViewerProps) {
  const [tab, setTab] = useState<TabKey>("reading");
  const { evidence, isLoading, error } = useDocumentData(documentId);

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <p className="py-10 text-center text-sm text-red-600">
        Failed to load document.
      </p>
    );
  }

  const segments = ((evidence?.segments ?? []) as Array<{ source?: string; target?: string }>).map(
    (s) => ({
      source: s.source ?? "",
      target: s.target ?? "",
    }),
  );

  return (
    <div>
      {/* Tab bar */}
      <div className="mb-4 flex gap-1 border-b border-gray-200">
        {(["reading", "judgment"] as TabKey[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "cursor-pointer border-b-2 px-4 py-2 text-sm font-medium transition-colors",
              tab === t
                ? "border-primary-600 text-primary-700"
                : "border-transparent text-gray-500 hover:text-gray-700",
            )}
          >
            {t === "reading" ? "Reading" : "Evidence Judgment"}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "reading" ? (
        <BilingualReadingPane
          segments={segments}
          sourceLang={evidence?.source_lang}
          targetLang={evidence?.target_lang}
        />
      ) : (
        <EvidenceJudgmentPane rawData={evidence?.raw_data} />
      )}
    </div>
  );
}
