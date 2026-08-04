
import { useState, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAccountCacheScope } from "@/features/auth/hooks/useAuthAccount";
import { fetchAllEvidence, readCachedAllEvidence } from "../services/variantDb";
import { aggregateVariants, filterAndPaginateVariants } from "../utils/variantAggregation";
import type {
  ClassificationLevel,
  ReviewStatusFilter,
  SortBy,
  SortOrder,
  SourceLanguageFilter,
  VariantIndexFilters,
} from "../types/variantDb";

const EVIDENCE_DB_FILTERS_KEY = "lingua:evidence-db:index-filters";
const DEFAULT_FILTERS: VariantIndexFilters = {
  page: 1,
  pageSize: 24,
};

const CLASSIFICATION_VALUES = new Set<ClassificationLevel>([
  "pathogenic",
  "likely_pathogenic",
  "uncertain",
  "likely_benign",
  "benign",
]);
const REVIEW_STATUS_VALUES = new Set<ReviewStatusFilter>([
  "provisional",
  "approved",
  "corrected",
  "rejected",
]);
const SOURCE_LANGUAGE_VALUES = new Set<SourceLanguageFilter>([
  "en",
  "zh",
  "ja",
  "de",
  "fr",
  "ru",
]);
const SORT_BY_VALUES = new Set<SortBy>([
  "gene",
  "variant",
  "disease",
  "classification",
  "evidence",
  "refs",
  "confidence",
  "updated",
]);
const SORT_ORDER_VALUES = new Set<SortOrder>(["asc", "desc"]);

function normalizeString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const normalized = value.trim();
  return normalized || undefined;
}

function normalizePositiveInt(value: unknown, fallback: number): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1) {
    return fallback;
  }
  return value;
}

function normalizeFilters(value: unknown): VariantIndexFilters {
  if (!value || typeof value !== "object") {
    return DEFAULT_FILTERS;
  }
  const candidate = value as Partial<Record<keyof VariantIndexFilters, unknown>>;
  const classification =
    typeof candidate.classification === "string" &&
    CLASSIFICATION_VALUES.has(candidate.classification as ClassificationLevel)
      ? (candidate.classification as ClassificationLevel)
      : undefined;
  const reviewStatus =
    typeof candidate.reviewStatus === "string" &&
    REVIEW_STATUS_VALUES.has(candidate.reviewStatus as ReviewStatusFilter)
      ? (candidate.reviewStatus as ReviewStatusFilter)
      : undefined;
  const sourceLanguage =
    typeof candidate.sourceLanguage === "string" &&
    SOURCE_LANGUAGE_VALUES.has(candidate.sourceLanguage as SourceLanguageFilter)
      ? (candidate.sourceLanguage as SourceLanguageFilter)
      : undefined;
  const sortBy =
    typeof candidate.sortBy === "string" && SORT_BY_VALUES.has(candidate.sortBy as SortBy)
      ? (candidate.sortBy as SortBy)
      : undefined;
  const sortOrder =
    typeof candidate.sortOrder === "string" && SORT_ORDER_VALUES.has(candidate.sortOrder as SortOrder)
      ? (candidate.sortOrder as SortOrder)
      : undefined;

  return {
    page: normalizePositiveInt(candidate.page, DEFAULT_FILTERS.page),
    pageSize: normalizePositiveInt(candidate.pageSize, DEFAULT_FILTERS.pageSize),
    gene: normalizeString(candidate.gene),
    variant: normalizeString(candidate.variant),
    disease: normalizeString(candidate.disease),
    classification,
    reviewStatus,
    sourceLanguage,
    sortBy,
    sortOrder,
  };
}

function loadFilters(): VariantIndexFilters {
  try {
    const raw = window.sessionStorage.getItem(EVIDENCE_DB_FILTERS_KEY);
    if (!raw) return DEFAULT_FILTERS;
    return normalizeFilters(JSON.parse(raw));
  } catch {
    return DEFAULT_FILTERS;
  }
}

function saveFilters(filters: VariantIndexFilters): void {
  try {
    window.sessionStorage.setItem(EVIDENCE_DB_FILTERS_KEY, JSON.stringify(filters));
  } catch {
    // Filter persistence is an enhancement.
  }
}

function clearSavedFilters(): void {
  try {
    window.sessionStorage.removeItem(EVIDENCE_DB_FILTERS_KEY);
  } catch {
    // Filter persistence is an enhancement.
  }
}

export function useVariantIndex() {
  const [filters, setFilters] = useState<VariantIndexFilters>(() => loadFilters());
  const accountCache = useAccountCacheScope();
  const queryScope = accountCache.isReady ? accountCache.scope : "auth-pending";

  // Fetch all evidence — we do client-side aggregation
  const query = useQuery({
    queryKey: ["evidence-db", "all-evidence", queryScope],
    queryFn: () =>
      fetchAllEvidence(
        {},
        { cacheScope: accountCache.scope, refresh: true },
      ),
    enabled: accountCache.isReady,
    initialData: () =>
      accountCache.isReady
        ? readCachedAllEvidence({}, accountCache.scope)
        : undefined,
    refetchOnMount: "always",
    staleTime: 0,
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
      setFilters((prev) => {
        const next = {
          ...prev,
          [key]: value,
          ...(key !== "page" ? { page: 1 } : {}),
        };
        saveFilters(next);
        return next;
      });
    },
    [],
  );

  const setPage = useCallback((page: number) => {
    setFilters((prev) => {
      const next = { ...prev, page };
      saveFilters(next);
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    clearSavedFilters();
    setFilters(DEFAULT_FILTERS);
  }, []);

  return {
    ...variantData,
    allEntries,
    isLoading: !accountCache.isReady || query.isLoading,
    isFetching: query.isFetching,
    error: accountCache.error ?? query.error,
    filters,
    updateFilter,
    setPage,
    clearFilters,
    refetch: query.refetch,
  };
}
