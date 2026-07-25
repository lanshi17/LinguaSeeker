import { useQuery } from "@tanstack/react-query";
import { fetchKnowledgeGraph } from "../services/graphRag";
import type { KnowledgeGraph } from "../types/graphRag";

export interface UseKnowledgeGraphOptions {
  geneSymbol?: string;
  diseaseName?: string;
  variantHgvsP?: string;
  phenotype?: string;
  hops?: number;
  mode?: string;
  limit?: number;
  enabled?: boolean;
}

export function useKnowledgeGraph(options: UseKnowledgeGraphOptions = {}) {
  const {
    geneSymbol,
    diseaseName,
    variantHgvsP,
    phenotype,
    hops = 2,
    mode = "full",
    limit = 200,
    enabled = true,
  } = options;

  return useQuery<KnowledgeGraph, Error>({
    queryKey: [
      "knowledgeGraph",
      geneSymbol,
      diseaseName,
      variantHgvsP,
      phenotype,
      hops,
      mode,
      limit,
    ],
    queryFn: () =>
      fetchKnowledgeGraph({
        geneSymbol,
        diseaseName,
        variantHgvsP,
        phenotype,
        hops,
        mode,
        limit,
      }),
    enabled:
      enabled &&
      Boolean(geneSymbol || diseaseName || variantHgvsP || phenotype),
  });
}
