import type { EvidenceSearchResult } from "@/features/evidence-search/types/evidenceSearch";
import type { VariantIndexEntry, VariantIndexData, VariantIndexFilters, ClassificationLevel } from "../types/variantDb";
import { classifyLevel, severityRank } from "./pathogenicity";

function makeVariantSlug(gene: string, variant: string, disease: string): string {
  const parts = [gene || "unknown", variant || "unknown"];
  if (disease) parts.push(disease);
  return parts.join(":");
}

function computeReviewStatus(statuses: string[]): string {
  if (statuses.includes("rejected")) return "rejected";
  if (statuses.includes("corrected")) return "corrected";
  if (statuses.includes("approved")) return "approved";
  return "provisional";
}

/**
 * Aggregate flat search results into variant-centric entries.
 * Groups by gene:variant:disease composite key.
 */
export function aggregateVariants(results: EvidenceSearchResult[]): VariantIndexEntry[] {
  const grouped = new Map<string, EvidenceSearchResult[]>();

  for (const result of results) {
    const gene = result.gene ?? "";
    const variant = result.variant ?? "";
    const disease = result.disease ?? "";
    const slug = makeVariantSlug(gene, variant, disease);

    const existing = grouped.get(slug);
    if (existing) {
      existing.push(result);
    } else {
      grouped.set(slug, [result]);
    }
  }

  const entries: VariantIndexEntry[] = [];

  for (const [slug, items] of grouped) {
    const first = items[0];
    const gene = first.gene ?? "";
    const variant = first.variant ?? "";
    const disease = first.disease ?? "";
    const classification = first.classification ?? "";

    const groupIds = items.map((r) => r.group_id);
    const sourceDocumentIds = [...new Set(items.map((r) => r.source_document_id))];

    // Weighted average confidence
    const totalFields = items.reduce((sum, r) => sum + r.field_count, 0);
    const weightedConfidence = items.reduce(
      (sum, r) => sum + (r.avg_confidence ?? 0) * r.field_count,
      0,
    );
    const avgConfidence = totalFields > 0 ? weightedConfidence / totalFields : 0;

    // Category distribution — approximate from field_count
    const categoryDistribution: Record<string, number> = {};
    // We don't have per-field data in search results, so distribute proportionally
    // This will be more accurate when we load group details
    const catKeys = ["A", "B", "D", "E", "J", "C", "F", "G", "H", "I"];
    for (const cat of catKeys) {
      categoryDistribution[cat] = 0;
    }
    // Assign field counts roughly — each group gets distributed across typical categories
    for (const item of items) {
      // Distribute evenly as an approximation
      const perCat = Math.floor(item.field_count / 3);
      const remainder = item.field_count % 3;
      categoryDistribution["A"] += perCat + (remainder > 0 ? 1 : 0);
      categoryDistribution["B"] += perCat + (remainder > 1 ? 1 : 0);
      categoryDistribution["E"] += perCat;
    }

    const reviewStatuses = items.map((r) => r.review_status);
    const classificationLevel = classifyLevel(classification);

    // Pick the most recent created_at
    const createdAt = items
      .map((r) => r.created_at)
      .filter(Boolean)
      .sort()
      .pop() ?? null;

    entries.push({
      variantSlug: slug,
      gene,
      variant,
      disease,
      classification,
      classificationLevel,
      evidenceGroupCount: items.length,
      literatureCount: sourceDocumentIds.length,
      avgConfidence,
      fieldCount: totalFields,
      categoryDistribution,
      reviewStatus: computeReviewStatus(reviewStatuses),
      createdAt,
      groupIds,
      sourceDocumentIds,
      representative: first,
    });
  }

  // Sort: pathogenic first, then by evidence count descending
  entries.sort((a, b) => {
    const rankDiff = severityRank(a.classificationLevel) - severityRank(b.classificationLevel);
    if (rankDiff !== 0) return rankDiff;
    return b.evidenceGroupCount - a.evidenceGroupCount;
  });

  return entries;
}

/**
 * Apply filters and pagination to aggregated variant entries.
 */
export function filterAndPaginateVariants(
  entries: VariantIndexEntry[],
  filters: VariantIndexFilters,
): VariantIndexData {
  let filtered = entries;

  if (filters.gene) {
    const q = filters.gene.toLowerCase();
    filtered = filtered.filter((e) => e.gene.toLowerCase().includes(q));
  }
  if (filters.variant) {
    const q = filters.variant.toLowerCase();
    filtered = filtered.filter((e) => e.variant.toLowerCase().includes(q));
  }
  if (filters.disease) {
    const q = filters.disease.toLowerCase();
    filtered = filtered.filter((e) => e.disease.toLowerCase().includes(q));
  }
  if (filters.classification) {
    filtered = filtered.filter((e) => e.classificationLevel === filters.classification);
  }

  const total = filtered.length;
  const start = (filters.page - 1) * filters.pageSize;
  const items = filtered.slice(start, start + filters.pageSize);

  // Compute aggregate stats
  const stats = {
    totalVariants: entries.length,
    totalEvidenceGroups: entries.reduce((s, e) => s + e.evidenceGroupCount, 0),
    totalLiterature: entries.reduce((s, e) => s + e.literatureCount, 0),
    avgConfidence:
      entries.length > 0
        ? entries.reduce((s, e) => s + e.avgConfidence, 0) / entries.length
        : 0,
    classificationDistribution: {
      pathogenic: 0,
      likely_pathogenic: 0,
      uncertain: 0,
      likely_benign: 0,
      benign: 0,
    } as Record<ClassificationLevel, number>,
  };

  for (const e of entries) {
    stats.classificationDistribution[e.classificationLevel]++;
  }

  return { items, total, page: filters.page, pageSize: filters.pageSize, stats };
}
