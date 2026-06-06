/** POST /evidence/search request body. */
export interface GraphSearchRequest {
  gene?: string;
  variant?: string;
  protein_change?: string;
  disease?: string;
}

/** A node in the evidence knowledge graph. */
export interface EvidenceGraphNode {
  node_id: string;
  label: string;
  node_type: string;
  properties?: Record<string, unknown>;
}

/** An edge in the evidence knowledge graph. */
export interface EvidenceGraphEdge {
  source_id: string;
  target_id: string;
  relationship: string;
  properties?: Record<string, unknown>;
}

/** POST /evidence/search response. */
export interface EvidenceSearchResponse {
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
  evidence_records: Record<string, unknown>[];
}
