import { useQuery } from "@tanstack/react-query";
import { useAccountCacheScope } from "@/features/auth/hooks/useAuthAccount";
import {
  fetchKnowledgeGraph,
  readCachedKnowledgeGraph,
} from "../services/graphRag";
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
  const accountCache = useAccountCacheScope();
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
  const params = {
    geneSymbol,
    diseaseName,
    variantHgvsP,
    phenotype,
    hops,
    mode,
    limit,
  };
  const queryScope = accountCache.isReady ? accountCache.scope : "auth-pending";

  const query = useQuery<KnowledgeGraph, Error>({
    queryKey: [
      "knowledgeGraph",
      geneSymbol,
      diseaseName,
      variantHgvsP,
      phenotype,
      hops,
      mode,
      limit,
      queryScope,
    ],
    queryFn: () =>
      fetchKnowledgeGraph(params, {
        cacheScope: accountCache.scope,
        refresh: true,
      }),
    initialData: () =>
      accountCache.isReady
        ? readCachedKnowledgeGraph(params, accountCache.scope)
        : undefined,
    refetchOnMount: "always",
    staleTime: 0,
    enabled:
      accountCache.isReady &&
      enabled &&
      Boolean(geneSymbol || diseaseName || variantHgvsP || phenotype),
  });

  return {
    ...query,
    error: accountCache.error ?? query.error,
  };
}
