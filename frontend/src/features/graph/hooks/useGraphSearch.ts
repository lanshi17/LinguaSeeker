"use client";

import { useMutation } from "@tanstack/react-query";
import {
  searchEvidenceGraph,
  getGraphStats,
  resyncDocument,
} from "../services/graph";
import type { GraphSearchRequest, EvidenceSearchResponse } from "../types/graph";

export function useGraphSearch() {
  const search = useMutation<EvidenceSearchResponse, Error, GraphSearchRequest>({
    mutationFn: searchEvidenceGraph,
  });

  const stats = useMutation({
    mutationFn: getGraphStats,
  });

  const resync = useMutation({
    mutationFn: (documentId: string) => resyncDocument(documentId),
  });

  return {
    search: search.mutateAsync,
    searchResults: search.data,
    isSearching: search.isPending,
    searchError: search.error,

    fetchStats: stats.mutateAsync,
    stats: stats.data,
    isLoadingStats: stats.isPending,

    resyncDocument: resync.mutateAsync,
    isResyncing: resync.isPending,
  };
}
