/** Graph node returned by the GraphRAG API. */
export interface GraphNode {
  node_id: string;
  labels: string[];
  display_name: string;
  properties: Record<string, unknown>;
}

/** Graph edge returned by the GraphRAG API. */
export interface GraphEdge {
  source_id: string;
  target_id: string;
  rel_type: string;
  properties: Record<string, unknown>;
}

/** Subgraph payload returned by /graphrag/graph. */
export interface KnowledgeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Citation to an evidence node. */
export interface GraphRagCitation {
  evidence_node_id: string;
  document_id: string | null;
  pmid: string | null;
  quote: string | null;
}

/** Request body for /graphrag/query. */
export interface GraphRagQueryRequest {
  question: string;
  hops?: number;
  mode?: string;
}

/** Response from /graphrag/query. */
export interface GraphRagQueryResponse {
  question: string;
  answer: string;
  subgraph: KnowledgeGraph;
  source_evidence_ids: string[];
  citations: GraphRagCitation[];
}

/** Graph visualization node for @antv/g6. */
export interface G6GraphNode {
  id: string;
  data: {
    label: string;
    type: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

/** Graph visualization edge for @antv/g6. */
export interface G6GraphEdge {
  id?: string;
  source: string;
  target: string;
  data: {
    label: string;
    [key: string]: unknown;
  };
}
