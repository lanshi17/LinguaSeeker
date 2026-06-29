import type {
  EvidenceFieldDistribution,
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
} from "@/features/evidence-search/types/evidenceSearch";
import { EVIDENCE_CATEGORIES } from "@/features/evidence-search/utils/evidenceDocument";

export interface ReviewProgress {
  total: number;
  reviewed: number;
  approved: number;
  corrected: number;
  rejected: number;
  provisional: number;
  reviewedPercent: number;
}

export interface EvidenceCoverage {
  coveredCategories: number;
  totalCategories: number;
  coveragePercent: number;
}

export interface VariantQualitySummary {
  reviewProgress: ReviewProgress;
  coverage: EvidenceCoverage;
  conflictCount: number;
}

export interface LiteratureQualitySummary {
  hasFullText: boolean;
  hasTranslation: boolean;
  reviewProgress: ReviewProgress;
  conflictCount: number;
}

export function computeReviewProgress(
  items: Array<Pick<EvidenceGroupItem, "review_status">>,
): ReviewProgress {
  const progress: ReviewProgress = {
    total: items.length,
    reviewed: 0,
    approved: 0,
    corrected: 0,
    rejected: 0,
    provisional: 0,
    reviewedPercent: 0,
  };

  for (const item of items) {
    switch (item.review_status) {
      case "approved":
        progress.approved += 1;
        break;
      case "corrected":
        progress.corrected += 1;
        break;
      case "rejected":
        progress.rejected += 1;
        break;
      default:
        progress.provisional += 1;
        break;
    }
  }

  progress.reviewed = progress.approved + progress.corrected + progress.rejected;
  progress.reviewedPercent =
    progress.total > 0 ? progress.reviewed / progress.total : 0;
  return progress;
}

export function computeCoverage(
  distribution: EvidenceFieldDistribution,
): EvidenceCoverage {
  const coveredCategories = EVIDENCE_CATEGORIES.filter(
    (category) => (distribution.by_category[category] ?? 0) > 0,
  ).length;
  const totalCategories = EVIDENCE_CATEGORIES.length;
  return {
    coveredCategories,
    totalCategories,
    coveragePercent:
      totalCategories > 0 ? coveredCategories / totalCategories : 0,
  };
}

export function computeVariantQuality(
  groups: EvidenceGroupDetailResponse[],
): VariantQualitySummary {
  const byCategory: Record<string, number> = {};
  const items = groups.flatMap((group) => group.items);

  for (const group of groups) {
    for (const [category, count] of Object.entries(group.distribution.by_category)) {
      byCategory[category] = (byCategory[category] ?? 0) + count;
    }
  }

  return {
    reviewProgress: computeReviewProgress(items),
    coverage: computeCoverage({
      by_category: byCategory,
      by_field: {},
      by_status: {},
      by_track: {},
    }),
    conflictCount: computeConflictCount(items),
  };
}

export function computeLiteratureQuality(
  detail: EvidenceGroupDetailResponse,
): LiteratureQualitySummary {
  return {
    hasFullText: hasFullText(detail),
    hasTranslation: hasTranslation(detail),
    reviewProgress: computeReviewProgress(detail.items),
    conflictCount: computeConflictCount(detail.items),
  };
}

export function computeConflictCount(items: EvidenceGroupItem[]): number {
  return items.filter((item) => {
    const category = item.category ?? null;
    return category === "H" || item.field_id.startsWith("H.");
  }).length;
}

export function hasFullText(detail: EvidenceGroupDetailResponse): boolean {
  return (
    Boolean(detail.original_document_text?.trim()) ||
    Boolean(detail.original_blocks?.length)
  );
}

export function hasTranslation(detail: EvidenceGroupDetailResponse): boolean {
  return (
    Boolean(detail.translated_document_text?.trim()) ||
    Boolean(detail.translated_blocks?.length) ||
    detail.traces.some((trace) => Boolean(trace.translated?.text.trim()))
  );
}
