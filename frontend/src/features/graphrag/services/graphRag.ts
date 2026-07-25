import { apiClient } from "@/lib/api/client";
import type {
  GraphRagQueryRequest,
  GraphRagQueryResponse,
  KnowledgeGraph,
} from "../types/graphRag";

export async function queryGraphRag(
  request: GraphRagQueryRequest,
): Promise<GraphRagQueryResponse> {
  const { data } = await apiClient.post<GraphRagQueryResponse>(
    "/graphrag/query",
    request,
  );
  return data;
}

export async function fetchKnowledgeGraph(params: {
  geneSymbol?: string;
  diseaseName?: string;
  variantHgvsP?: string;
  phenotype?: string;
  hops?: number;
  mode?: string;
  limit?: number;
}): Promise<KnowledgeGraph> {
  const { data } = await apiClient.get<KnowledgeGraph>("/graphrag/graph", {
    params: {
      gene_symbol: params.geneSymbol,
      disease_name: params.diseaseName,
      variant_hgvs_p: params.variantHgvsP,
      phenotype: params.phenotype,
      hops: params.hops ?? 2,
      mode: params.mode ?? "full",
      limit: params.limit ?? 200,
    },
  });
  return data;
}
