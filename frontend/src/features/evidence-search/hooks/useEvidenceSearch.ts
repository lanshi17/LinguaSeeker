
import { useRef, useState, useCallback } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { searchEvidence } from "../services/evidenceSearch";
import type { EvidenceSearchQuery } from "../types/evidenceSearch";

const DEFAULT_PAGE_SIZE = 50;

export function useEvidenceSearch() {
  const [filters, setFilters] = useState<EvidenceSearchQuery>({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
  });

  const query = useQuery({
    queryKey: ["evidence", "search", filters],
    queryFn: () => searchEvidence(filters),
    placeholderData: keepPreviousData,
  });
  const refetchRef = useRef(query.refetch);
  refetchRef.current = query.refetch;

  const updateFilter = useCallback(
    (key: keyof EvidenceSearchQuery, value: string) => {
      setFilters((prev) => ({
        ...prev,
        [key]: value || undefined,
        page: key !== "page" ? 1 : prev.page,
      }));
    },
    [],
  );

  const setPage = useCallback((page: number) => {
    setFilters((prev) => ({ ...prev, page }));
  }, []);

  const applyFilters = useCallback(() => {
    void refetchRef.current();
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({ page: 1, page_size: DEFAULT_PAGE_SIZE });
  }, []);

  return {
    results: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    page: query.data?.page ?? 1,
    pageSize: query.data?.page_size ?? DEFAULT_PAGE_SIZE,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    filters,
    updateFilter,
    applyFilters,
    clearFilters,
    setPage,
  };
}
