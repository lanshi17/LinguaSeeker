import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { useAccountCacheScope } from "@/features/auth/hooks/useAuthAccount";
import {
  fetchKnowledgeGraph,
  isKnowledgeGraphNoMatchError,
  readCachedKnowledgeGraph,
} from "../services/graphRag";
import { demoKnowledgeGraph } from "../services/demoGraph";
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

export interface UseKnowledgeGraphResult {
  /**
   * The graph to render. When the backend hasn't returned yet, returned an
   * empty graph, or hit a "no matching nodes" 400, this falls back to the
   * demo graph so the canvas never looks empty.
   */
  data: KnowledgeGraph | undefined;
  /**
   * True when `data` is the built-in demo placeholder rather than real
   * backend data. Components use this to show a "sample data" badge.
   */
  isDemo: boolean;
  isFetching: boolean;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useKnowledgeGraph(
  options: UseKnowledgeGraphOptions = {},
): UseKnowledgeGraphResult {
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
    // A 400 "no matching nodes" response is a deterministic empty-result
    // signal from older backends (newer ones return 200 with an empty graph).
    // Retrying it only produces repeated failing requests in the console.
    retry: (_failureCount, error) => !isKnowledgeGraphNoMatchError(error),
    enabled:
      accountCache.isReady &&
      enabled &&
      Boolean(geneSymbol || diseaseName || variantHgvsP || phenotype),
  });

  const { data, isError, error, isFetching, isPending, refetch } = query;

  const { displayData, isDemo } = useMemo(() => {
    // Real data with nodes — always use it.
    if (data && data.nodes.length > 0) {
      return { displayData: data, isDemo: false };
    }
    // No real data yet, or real data is empty, or it's a no-match error.
    // Show the demo graph so the canvas stays visually populated while the
    // backend catches up (or while Neo4j gets seeded on a fresh environment).
    if (
      !data ||
      data.nodes.length === 0 ||
      (isError && isKnowledgeGraphNoMatchError(error))
    ) {
      return { displayData: demoKnowledgeGraph, isDemo: true };
    }
    return { displayData: data, isDemo: false };
  }, [data, isError, error]);

  return {
    data: displayData,
    isDemo,
    isFetching,
    isPending,
    isError,
    error: accountCache.error ?? error ?? null,
    refetch,
  };
}
