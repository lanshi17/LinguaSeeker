
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAllEvidence, fetchEvidenceGroupDetail } from "../services/variantDb";
import { aggregateVariants } from "../utils/variantAggregation";
import type { VariantDetailData, LiteratureReference } from "../types/variantDb";
import type { EvidenceGroupDetailResponse } from "@/features/evidence-search/types/evidenceSearch";

/** Extract category letter from field_id */
function categoryFromFieldId(fieldId: string): string | null {
  if (!fieldId) return null;
  const letter = fieldId.split(".")[0];
  return "ABCDEFGHIJ".includes(letter) ? letter : null;
}

function buildLiteratureReferences(
  groups: EvidenceGroupDetailResponse[],
): LiteratureReference[] {
  return groups.map((g) => {
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
    };
  });
}

export function useVariantDetail(variantSlug: string) {
  // First, get the variant index to find group IDs
  const indexQuery = useQuery({
    queryKey: ["evidence-db", "all-evidence"],
    queryFn: () => fetchAllEvidence({ page: 1, page_size: 200 }),
    staleTime: 60_000,
  });

  const entry = useMemo(() => {
    if (!indexQuery.data?.items) return null;
    const entries = aggregateVariants(indexQuery.data.items);
    return entries.find((e) => e.variantSlug === variantSlug) ?? null;
  }, [indexQuery.data, variantSlug]);

  // Fetch details for each group
  const groupIds = entry?.groupIds ?? [];

  const groupQueries = useQuery({
    queryKey: ["evidence-db", "variant-groups", variantSlug, groupIds],
    queryFn: async () => {
      const results = await Promise.allSettled(
        groupIds.map((id) => fetchEvidenceGroupDetail(id)),
      );
      return results
        .filter(
          (r): r is PromiseFulfilledResult<EvidenceGroupDetailResponse> =>
            r.status === "fulfilled",
        )
        .map((r) => r.value);
    },
    enabled: groupIds.length > 0,
    staleTime: 60_000,
  });

  const detail = useMemo((): VariantDetailData | null => {
    if (!entry || !groupQueries.data) return null;

    const evidenceGroups = groupQueries.data;
    const literature = buildLiteratureReferences(evidenceGroups);
    const allItems = evidenceGroups.flatMap((g) => g.items);

    return { entry, evidenceGroups, literature, allItems };
  }, [entry, groupQueries.data]);

  return {
    detail,
    isLoading: indexQuery.isLoading || groupQueries.isLoading,
    isFetching: indexQuery.isFetching || groupQueries.isFetching,
    error: indexQuery.error ?? groupQueries.error,
  };
}
