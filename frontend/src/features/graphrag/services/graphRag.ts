import { apiClient, readCachedApiResponse } from "@/lib/api/client";
import type {
  GraphRagQueryRequest,
  GraphRagQueryResponse,
  KnowledgeGraph,
} from "../types/graphRag";

// GraphRAG queries run two sequential LLM calls (entity extraction + answer
// generation), so they routinely exceed the global 30s client timeout.
const GRAPH_RAG_QUERY_TIMEOUT_MS = 120_000;
const KNOWLEDGE_GRAPH_TIMEOUT_MS = 60_000;

export interface KnowledgeGraphParams {
  geneSymbol?: string;
  diseaseName?: string;
  variantHgvsP?: string;
  phenotype?: string;
  hops?: number;
  mode?: string;
  limit?: number;
}

interface FetchKnowledgeGraphOptions {
  cacheScope?: string;
  refresh?: boolean;
}

function buildKnowledgeGraphParams(params: KnowledgeGraphParams) {
  return {
    gene_symbol: params.geneSymbol,
    disease_name: params.diseaseName,
    variant_hgvs_p: params.variantHgvsP,
    phenotype: params.phenotype,
    hops: params.hops ?? 2,
    mode: params.mode ?? "full",
    limit: params.limit ?? 200,
  };
}

export async function queryGraphRag(
  request: GraphRagQueryRequest,
): Promise<GraphRagQueryResponse> {
  const { data } = await apiClient.post<GraphRagQueryResponse>(
    "/graphrag/query",
    request,
    { timeout: GRAPH_RAG_QUERY_TIMEOUT_MS },
  );
  return data;
}

export async function fetchKnowledgeGraph(
  params: KnowledgeGraphParams,
  options: FetchKnowledgeGraphOptions = {},
): Promise<KnowledgeGraph> {
  const { data } = await apiClient.get<KnowledgeGraph>("/graphrag/graph", {
    headers: options.refresh ? { "Cache-Control": "no-cache" } : undefined,
    timeout: KNOWLEDGE_GRAPH_TIMEOUT_MS,
    params: buildKnowledgeGraphParams(params),
    responseCache: { scope: options.cacheScope },
  });
  return data;
}

export function readCachedKnowledgeGraph(
  params: KnowledgeGraphParams,
  cacheScope?: string,
): KnowledgeGraph | undefined {
  return readCachedApiResponse<KnowledgeGraph>(
    "/graphrag/graph",
    buildKnowledgeGraphParams(params),
    cacheScope,
  );
}

/**
 * True when the backend reports that no nodes matched the query.
 *
 * Older backends return 400 for an empty result set; treat that as an empty
 * graph so the explorer shows its empty state instead of an error card.
 */
export function isKnowledgeGraphNoMatchError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const candidate = error as { backendMessage?: unknown; status?: unknown };
  return (
    candidate.status === 400 &&
    typeof candidate.backendMessage === "string" &&
    /no matching nodes/i.test(candidate.backendMessage)
  );
}
