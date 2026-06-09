/** Query parameters for evidence search. */
export interface EvidenceSearchQuery {
  gene?: string;
  variant?: string;
  disease?: string;
  pmid?: string;
  doi?: string;
  page?: number;
  page_size?: number;
}

/**
 * A single evidence search result (pivoted from field-level extractions).
 */
export interface EvidenceSearchResult {
  group_id: string;
  source_document_id: string;
  title?: string | null;
  pmid?: string | null;
  doi?: string | null;
  gene?: string | null;
  variant?: string | null;
  disease?: string | null;
  classification?: string | null;
  field_count: number;
  avg_confidence?: number | null;
  review_status: string;
  canonical_evidence_id?: string | null;
}

/** GET /api/v1/evidence/search response. */
export interface EvidenceSearchResponse {
  items: EvidenceSearchResult[];
  total: number;
  page: number;
  page_size: number;
}

export interface EvidenceFieldDistribution {
  by_category: Record<string, number>;
  by_field: Record<string, number>;
  by_status: Record<string, number>;
  by_track: Record<string, number>;
}

export interface EvidenceGroupItem {
  canonical_evidence_id: string;
  field_id: string;
  field_name?: string | null;
  category?: string | null;
  value?: string | null;
  review_status: string;
  confidence?: number | null;
  track?: string | null;
  page?: number | null;
}

export type EvidenceHighlightTone =
  | "classification"
  | "disease"
  | "functional"
  | "gene"
  | "neutral"
  | "variant";

export interface EvidenceChainHighlight {
  text: string;
  highlight_start: number;
  highlight_end: number;
  page?: number | null;
  source_span: Record<string, unknown>;
}

export interface EvidenceTrackTrace {
  canonical_evidence_id: string;
  field_id: string;
  field_name?: string | null;
  original_value?: string | null;
  translated_value?: string | null;
  original?: EvidenceChainHighlight | null;
  translated?: EvidenceChainHighlight | null;
  alignment_confidence?: number | null;
}

export interface EvidenceGroupDetailResponse {
  group_id: string;
  source_document_id: string;
  title?: string | null;
  pmid?: string | null;
  doi?: string | null;
  original_document_text?: string | null;
  translated_document_text?: string | null;
  gene?: string | null;
  variant?: string | null;
  disease?: string | null;
  classification?: string | null;
  item_count: number;
  avg_confidence?: number | null;
  distribution: EvidenceFieldDistribution;
  items: EvidenceGroupItem[];
  traces: EvidenceTrackTrace[];
}
