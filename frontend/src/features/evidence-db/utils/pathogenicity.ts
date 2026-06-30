import type { ClassificationLevel } from "../types/variantDb";

/** Map a classification string to a severity level */
export function classifyLevel(classification?: string | null): ClassificationLevel {
  const lower = (classification ?? "").toLowerCase().trim();
  if (!lower || lower === "not specified" || lower === "unknown") return "uncertain";

  if (lower === "pathogenic" || lower.includes("pathogenic") && !lower.includes("likely") && !lower.includes("benign")) {
    return "pathogenic";
  }
  if (lower.includes("likely pathogenic") || lower === "lp") return "likely_pathogenic";

  if (lower === "benign" || lower.includes("benign") && !lower.includes("likely") && !lower.includes("pathogenic")) {
    return "benign";
  }
  if (lower.includes("likely benign") || lower === "lb") return "likely_benign";

  if (lower.includes("uncertain") || lower.includes("vus") || lower.includes("conflicting")) return "uncertain";

  return "uncertain";
}

const SEVERITY_ORDER: ClassificationLevel[] = [
  "pathogenic",
  "likely_pathogenic",
  "uncertain",
  "likely_benign",
  "benign",
];

export function severityRank(level: ClassificationLevel): number {
  return SEVERITY_ORDER.indexOf(level);
}

export function worstClassification(levels: ClassificationLevel[]): ClassificationLevel {
  if (levels.length === 0) return "uncertain";
  return levels.reduce((worst, current) =>
    severityRank(current) < severityRank(worst) ? current : worst,
  );
}

/**
 * CSS hex color for a classification level.
 * High-contrast colors that meet WCAG AA on white backgrounds.
 */
export function classificationColor(level: ClassificationLevel): string {
  switch (level) {
    case "pathogenic": return "#B91C1C";
    case "likely_pathogenic": return "#DC2626";
    case "uncertain": return "#6B7280";
    case "likely_benign": return "#0D9488";
    case "benign": return "#0F766E";
  }
}

export function classificationLabel(level: ClassificationLevel, t?: (key: string) => string): string {
  if (t) {
    switch (level) {
      case "pathogenic": return t("evidenceDb.class.pathogenic");
      case "likely_pathogenic": return t("evidenceDb.class.likelyPathogenic");
      case "uncertain": return t("evidenceDb.class.vus");
      case "likely_benign": return t("evidenceDb.class.likelyBenign");
      case "benign": return t("evidenceDb.class.benign");
    }
  }
  switch (level) {
    case "pathogenic": return "Pathogenic";
    case "likely_pathogenic": return "Likely Pathogenic";
    case "uncertain": return "VUS";
    case "likely_benign": return "Likely Benign";
    case "benign": return "Benign";
  }
}

export function classificationShortLabel(level: ClassificationLevel): string {
  switch (level) {
    case "pathogenic": return "P";
    case "likely_pathogenic": return "LP";
    case "uncertain": return "VUS";
    case "likely_benign": return "LB";
    case "benign": return "B";
  }
}
