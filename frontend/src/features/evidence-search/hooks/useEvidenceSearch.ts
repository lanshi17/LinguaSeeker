"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchEvidence } from "../services/evidenceSearch";
import type { EvidenceSearchQuery } from "../types/evidenceSearch";

/**
 * Evidence search hook with auto-fetch on mount.
 *
 * Loads all evidence on initial mount (empty query).
 * User can then narrow results by setting filter fields.
 * Refetches automatically when filters change (via refetch()).
 */
export function useEvidenceSearch() {
  const [filters, setFilters] = useState<EvidenceSearchQuery>({});

  const query = useQuery({
    queryKey: ["evidence", "search", filters],
    queryFn: () => searchEvidence(filters),
  });

  const updateFilter = useCallback(
    (key: keyof EvidenceSearchQuery, value: string) => {
      setFilters((prev) => ({
        ...prev,
        [key]: value || undefined,
      }));
    },
    [],
  );

  const applyFilters = useCallback(() => {
    query.refetch();
  }, [query]);

  const clearFilters = useCallback(() => {
    setFilters({});
  }, []);

  return {
    results: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    filters,
    updateFilter,
    applyFilters,
    clearFilters,
  };
}
