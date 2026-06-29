
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAllEvidence, fetchEvidenceGroupDetail } from "../services/variantDb";
import {
  aggregateVariants,
  buildVariantGroupDocumentPairs,
  chooseVariantSearchRows,
  parseVariantSlug,
} from "../utils/variantAggregation";
import { computeLiteratureQuality, computeVariantQuality } from "../utils/fieldModel";
import type { VariantDetailData, LiteratureReference, VariantIndexEntry } from "../types/variantDb";
import type { EvidenceGroupDetailResponse, EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";

/** Extract category letter from field_id */
function categoryFromFieldId(fieldId: string): string | null {
  if (!fieldId) return null;
  const letter = fieldId.split(".")[0];
  return "ABCDEFGHIJ".includes(letter) ? letter : null;
}

function buildBilingualMap(
  items: EvidenceGroupItem[],
): Map<string, { original?: EvidenceGroupItem; translated?: EvidenceGroupItem }> {
  const map = new Map<string, { original?: EvidenceGroupItem; translated?: EvidenceGroupItem }>();
  for (const item of items) {
    if (item.track !== "original" && item.track !== "translated") continue;
    let entry = map.get(item.canonical_evidence_id);
    if (!entry) {
      entry = {};
      map.set(item.canonical_evidence_id, entry);
    }
    if (item.track === "original") entry.original = item;
    else entry.translated = item;
  }
  return map;
}

function buildLiteratureReferences(
  groups: EvidenceGroupDetailResponse[],
): LiteratureReference[] {
  // Deduplicate by source_document_id — the same paper should appear only
  // once even when multiple (group_id, source_document_id) pairs exist.
  const seenDocs = new Set<string>();
  const deduped: EvidenceGroupDetailResponse[] = [];
  for (const g of groups) {
    if (!seenDocs.has(g.source_document_id)) {
      seenDocs.add(g.source_document_id);
      deduped.push(g);
    }
  }

  return deduped.map((g) => {
    const categories = new Set<string>();
    const quality = computeLiteratureQuality(g);
    for (const item of g.items) {
      const cat = item.category ?? categoryFromFieldId(item.field_id);
      if (cat) categories.add(cat);
    }

    return {
      sourceDocumentId: g.source_document_id,
      title: g.title ?? "Untitled",
      pmid: g.pmid ?? undefined,
      doi: g.doi ?? undefined,
      groupId: g.group_id,
      fieldCount: g.item_count,
      avgConfidence: g.avg_confidence ?? 0,
      reviewStatus: "provisional",
      categories: [...categories].sort(),
      bilingualItems: buildBilingualMap(g.items),
      ...quality,
    };
  });
}

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
