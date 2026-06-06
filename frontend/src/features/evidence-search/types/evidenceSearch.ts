/** Query parameters for evidence search. */
export interface EvidenceSearchQuery {
  gene?: string;
  variant?: string;
  disease?: string;
  pmid?: string;
  doi?: string;
  limit?: number;
}

/** A single evidence search result. */
export interface EvidenceSearchResult {
  canonical_evidence_id: string;
  pmid?: string;
  doi?: string;
  gene_ids?: string[];
  variant_ids?: string[];
  review_status?: string;
  current_best_confidence?: number;
  active_payload?: EvidencePayload;
}

/** Structured evidence card payload. */
export interface EvidencePayload {
  gene?: string;
  variant?: string;
  phenotype?: string;
  disease?: string;
  classification?: string;
  evidence_strength?: string;
  evidence_type?: string;
  functional_impact?: string;
  inheritance_pattern?: string;
  zygosity?: string;
  references?: string[];
  summary?: string;
}

/** Search API response. */
export interface EvidenceSearchResponse {
  items: EvidenceSearchResult[];
  total: number;
}
