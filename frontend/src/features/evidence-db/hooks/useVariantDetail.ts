
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAllEvidence, fetchEvidenceGroupDetail } from "../services/variantDb";
import {
  aggregateVariants,
  buildVariantGroupDocumentPairs,
  chooseVariantSearchRows,
  parseVariantSlug,
} from "../utils/variantAggregation";
import { computeVariantQuality } from "../utils/fieldModel";
import { buildLiteratureReferences, buildBilingualMap } from "../utils/variantDetailHelpers";
import type { VariantDetailData, VariantIndexEntry } from "../types/variantDb";
import type { EvidenceGroupDetailResponse } from "@/features/evidence-search/types/evidenceSearch";

export function useVariantDetail(variantSlug: string, seededEntry?: VariantIndexEntry) {
  const variantFilters = useMemo(() => parseVariantSlug(variantSlug), [variantSlug]);
  const hasSeededEntry = seededEntry?.variantSlug === variantSlug;

  // First, get search rows scoped to this variant so detail pages do not
  // load the full evidence index.
  const indexQuery = useQuery({
    queryKey: ["evidence-db", "variant-search", variantSlug, variantFilters],
    queryFn: () => fetchAllEvidence({ ...variantFilters, page: 1, page_size: 1000 }),
    enabled: !hasSeededEntry,
    staleTime: 60_000,
  });

  const fullIndexQuery = useQuery({
    queryKey: ["evidence-db", "all-evidence"],
    queryFn: () => fetchAllEvidence({ page: 1, page_size: 1000 }),
    enabled:
      !hasSeededEntry &&
      Boolean(indexQuery.data) &&
      buildVariantGroupDocumentPairs(indexQuery.data?.items ?? [], variantSlug).length === 0,
    staleTime: 60_000,
  });

  const searchRows = useMemo(
    () =>
      chooseVariantSearchRows(
        indexQuery.data?.items ?? [],
        fullIndexQuery.data?.items ?? [],
        variantSlug,
      ),
    [fullIndexQuery.data, indexQuery.data, variantSlug],
  );

  const entry = useMemo(() => {
    if (hasSeededEntry) return seededEntry;
    if (!indexQuery.data?.items) return null;
    const entries = aggregateVariants(searchRows);
    return entries.find((e) => e.variantSlug === variantSlug) ?? null;
  }, [hasSeededEntry, indexQuery.data, searchRows, seededEntry, variantSlug]);

  const groupDocPairs = useMemo(() => {
    if (hasSeededEntry && seededEntry.groupDocumentPairs.length > 0) {
      return seededEntry.groupDocumentPairs;
    }
    if (!indexQuery.data?.items || !entry) return [];
    return buildVariantGroupDocumentPairs(searchRows, variantSlug);
  }, [entry, hasSeededEntry, indexQuery.data, searchRows, seededEntry, variantSlug]);

  const groupQueries = useQuery({
    queryKey: ["evidence-db", "variant-groups", variantSlug, groupDocPairs],
    queryFn: async () => {
      const results = await Promise.allSettled(
        groupDocPairs.map((pair) =>
          fetchEvidenceGroupDetail(pair.groupId, pair.sourceDocumentId),
        ),
      );
      return results
        .filter(
          (r): r is PromiseFulfilledResult<EvidenceGroupDetailResponse> =>
            r.status === "fulfilled",
        )
        .map((r) => r.value);
    },
    enabled: groupDocPairs.length > 0,
    staleTime: 60_000,
  });

  const detail = useMemo((): VariantDetailData | null => {
    if (!entry || !groupQueries.data) return null;

    const evidenceGroups = groupQueries.data;
    const literature = buildLiteratureReferences(evidenceGroups);
    const seenIds = new Set<string>();
    const allItems = evidenceGroups.flatMap((g) =>
      g.items.filter((item) => {
        if (seenIds.has(item.canonical_evidence_id)) return false;
        seenIds.add(item.canonical_evidence_id);
        return true;
      }),
    );

    const reconciledItems = allItems.filter((item) => item.track === "reconciled");
    const bilingualItems = buildBilingualMap(
      evidenceGroups.flatMap((g) => g.items),
    );

    return {
      entry,
      evidenceGroups,
      literature,
      allItems,
      reconciledItems,
      bilingualItems,
      quality: computeVariantQuality(evidenceGroups),
    };
  }, [entry, groupQueries.data]);

  return {
    detail,
    isLoading: indexQuery.isLoading || fullIndexQuery.isLoading || groupQueries.isLoading,
    isFetching: indexQuery.isFetching || fullIndexQuery.isFetching || groupQueries.isFetching,
    error: indexQuery.error ?? fullIndexQuery.error ?? groupQueries.error,
  };
}
