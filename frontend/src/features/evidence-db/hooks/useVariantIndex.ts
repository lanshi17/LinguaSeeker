
import { useState, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAllEvidence } from "../services/variantDb";
import { aggregateVariants, filterAndPaginateVariants } from "../utils/variantAggregation";
import type { VariantIndexFilters } from "../types/variantDb";

const DEFAULT_FILTERS: VariantIndexFilters = {
  page: 1,
  pageSize: 24,
};

export function useVariantIndex() {
  const [filters, setFilters] = useState<VariantIndexFilters>(DEFAULT_FILTERS);

  // Fetch all evidence — we do client-side aggregation
  const query = useQuery({
    queryKey: ["evidence-db", "all-evidence"],
    queryFn: () => fetchAllEvidence({ page: 1, page_size: 200 }),
    staleTime: 60_000,
  });

  // Aggregate into variant-centric entries
  const allEntries = useMemo(
    () => (query.data?.items ? aggregateVariants(query.data.items) : []),
    [query.data],
  );

  // Apply filters and pagination
  const variantData = useMemo(
    () => filterAndPaginateVariants(allEntries, filters),
    [allEntries, filters],
  );

  const updateFilter = useCallback(
    <K extends keyof VariantIndexFilters>(key: K, value: VariantIndexFilters[K]) => {
      setFilters((prev) => ({
        ...prev,
        [key]: value,
        ...(key !== "page" ? { page: 1 } : {}),
      }));
    },
    [],
  );

  const setPage = useCallback((page: number) => {
    setFilters((prev) => ({ ...prev, page }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  return {
    ...variantData,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    filters,
    updateFilter,
    setPage,
    clearFilters,
    refetch: query.refetch,
  };
}
