/**
 * Pure helper functions for variant detail data transformation.
 * Extracted from useVariantDetail to reduce hook complexity.
 */

import { computeLiteratureQuality } from "./fieldModel";
import type { LiteratureReference } from "../types/variantDb";
import type { EvidenceGroupDetailResponse, EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";

/** Extract category letter from field_id (e.g. "A.gene_symbol" → "A"). */
export function categoryFromFieldId(fieldId: string): string | null {
  if (!fieldId) return null;
  const letter = fieldId.split(".")[0];
  return "ABCDEFGHIJ".includes(letter) ? letter : null;
}

/** Build a map of canonical_evidence_id → { original, translated } items. */
export function buildBilingualMap(
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

/**
 * Build literature references from evidence group details.
 * Deduplicates by source_document_id.
 */
export function buildLiteratureReferences(
  groups: EvidenceGroupDetailResponse[],
): LiteratureReference[] {
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
