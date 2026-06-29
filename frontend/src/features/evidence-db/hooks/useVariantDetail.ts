
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAllEvidence, fetchEvidenceGroupDetail } from "../services/variantDb";
import {
  aggregateVariants,
  buildVariantGroupDocumentPairs,
  parseVariantSlug,
} from "../utils/variantAggregation";
import type { VariantDetailData, LiteratureReference } from "../types/variantDb";
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
    };
  });
}

export function useVariantDetail(variantSlug: string) {
  const variantFilters = useMemo(() => parseVariantSlug(variantSlug), [variantSlug]);

  // First, get search rows scoped to this variant so detail pages do not
  // load the full evidence index.
  const indexQuery = useQuery({
    queryKey: ["evidence-db", "variant-search", variantSlug, variantFilters],
    queryFn: () => fetchAllEvidence({ ...variantFilters, page: 1, page_size: 1000 }),
    staleTime: 60_000,
  });

  const entry = useMemo(() => {
    if (!indexQuery.data?.items) return null;
    const entries = aggregateVariants(indexQuery.data.items);
    return entries.find((e) => e.variantSlug === variantSlug) ?? null;
  }, [indexQuery.data, variantSlug]);

  const groupDocPairs = useMemo(() => {
    if (!indexQuery.data?.items || !entry) return [];
    return buildVariantGroupDocumentPairs(indexQuery.data.items, variantSlug);
  }, [entry, indexQuery.data, variantSlug]);

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

    return { entry, evidenceGroups, literature, allItems, reconciledItems, bilingualItems };
  }, [entry, groupQueries.data]);

  return {
    detail,
    isLoading: indexQuery.isLoading || groupQueries.isLoading,
    isFetching: indexQuery.isFetching || groupQueries.isFetching,
    error: indexQuery.error ?? groupQueries.error,
  };
}
