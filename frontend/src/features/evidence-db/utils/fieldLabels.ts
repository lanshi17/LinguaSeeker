import type { TFunction } from "@/lib/i18n";

export interface EvidenceDbLabels {
  avgConfidence: string;
  categories: string;
  confidence: string;
  coverage: string;
  evidenceFields: string;
  evidenceGroups: string;
  exportReport: string;
  fieldCount: string;
  literature: string;
  literatureSources: string;
  reviewProgress: string;
  reviewed: string;
  updated: string;
  uniqueVariants: string;
}

export function getEvidenceDbLabels(t: TFunction): EvidenceDbLabels {
  return {
    avgConfidence: t("evidenceDb.label.avgConfidence"),
    categories: t("evidenceDb.label.categories"),
    confidence: t("evidenceDb.label.confidence"),
    coverage: t("evidenceDb.label.coverage"),
    evidenceFields: t("evidenceDb.label.evidenceFields"),
    evidenceGroups: t("evidenceDb.label.evidenceGroups"),
    exportReport: t("evidenceDb.label.exportReport"),
    fieldCount: t("evidenceDb.label.fieldCount"),
    literature: t("evidenceDb.label.literature"),
    literatureSources: t("evidenceDb.label.litSources"),
    reviewProgress: t("evidenceDb.label.reviewProgress"),
    reviewed: t("evidenceDb.label.reviewed"),
    updated: t("evidenceDb.label.updated"),
    uniqueVariants: t("evidenceDb.label.uniqueVariants"),
  };
}

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

export function formatReviewedCount(progress: ReviewCountLike, t?: TFunction): string {
  const reviewedLabel = t ? t("evidenceDb.label.reviewed") : "Reviewed";
  return `${reviewedLabel} ${progress.reviewed}/${progress.total}`;
}

export function formatCoverageCount(coverage: CoverageCountLike): string {
  return `${coverage.coveredCategories}/${coverage.totalCategories}`;
}
