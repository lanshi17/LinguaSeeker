/** Evidence counts grouped by review status. */
export interface EvidenceByStatus {
  provisional: number;
  approved: number;
  corrected: number;
  rejected: number;
}

/** Lightweight processing run info. */
export interface ProcessingRunSummary {
  processing_run_id: string;
  source_document_id: string;
  run_status: string;
  created_at: string | null;
  completed_at: string | null;
}

/** Aggregated dashboard metrics from GET /api/v1/dashboard/summary. */
export interface DashboardSummary {
  total_documents: number;
  total_processing_runs: number;
  total_evidence_items: number;
  evidence_by_status: EvidenceByStatus;
  avg_confidence: number | null;
  recent_runs: ProcessingRunSummary[];
}
