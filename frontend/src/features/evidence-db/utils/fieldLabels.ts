export const EVIDENCE_DB_LABELS = {
  avgConfidence: "Avg Confidence",
  categories: "Categories",
  confidence: "Confidence",
  coverage: "Coverage",
  evidenceFields: "Evidence fields",
  evidenceGroups: "Evidence Groups",
  exportReport: "Export report",
  literature: "Literature",
  literatureSources: "Literature Sources",
  reviewProgress: "Review progress",
  reviewed: "Reviewed",
  updated: "Updated",
  uniqueVariants: "Unique Variants",
} as const;

export interface ReviewCountLike {
  reviewed: number;
  total: number;
}

export interface CoverageCountLike {
  coveredCategories: number;
  totalCategories: number;
}

export function formatConfidencePercent(value?: number | null): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

export function formatReviewedCount(progress: ReviewCountLike): string {
  return `${EVIDENCE_DB_LABELS.reviewed} ${progress.reviewed}/${progress.total}`;
}

export function formatCoverageCount(coverage: CoverageCountLike): string {
  return `${coverage.coveredCategories}/${coverage.totalCategories}`;
}
