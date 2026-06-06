"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";

/** A single bilingual text segment from the document. */
export interface DocumentSegment {
  source: string;
  target: string;
}

interface DocumentEvidencePayload {
  document_id: string;
  source_lang?: string;
  target_lang?: string;
  segments?: DocumentSegment[];
  raw_data?: unknown;
}

interface PaperTaskDetail {
  paper_task_id: string;
  status: string;
  result_payload?: unknown;
}

/**
 * Fetches document evidence + paper detail for the DocumentViewer.
 */
export function useDocumentData(documentId: string) {
  const evidence = useQuery({
    queryKey: ["document", "evidence", documentId],
    queryFn: async () => {
      const { data } = await apiClient.get<DocumentEvidencePayload>(
        `/evidence/document/${documentId}`,
      );
      return data;
    },
    enabled: !!documentId,
  });

  const paperDetail = useQuery({
    queryKey: ["document", "paper", documentId],
    queryFn: async () => {
      const { data } = await apiClient.get<PaperTaskDetail>(
        `/tasks/papers/${documentId}`,
      );
      return data;
    },
    enabled: !!documentId,
  });

  return {
    evidence: evidence.data,
    paperDetail: paperDetail.data,
    isLoading: evidence.isLoading || paperDetail.isLoading,
    error: evidence.error ?? paperDetail.error,
  };
}
