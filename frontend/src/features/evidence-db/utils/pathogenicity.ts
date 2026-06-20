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

/** Tailwind classes for classification badge — light theme, accessible contrast */
export function classificationBadgeClasses(level: ClassificationLevel): string {
  switch (level) {
    case "pathogenic": return "bg-red-100 text-red-800 border-red-200";
    case "likely_pathogenic": return "bg-red-50 text-red-700 border-red-200";
    case "uncertain": return "bg-gray-100 text-gray-700 border-gray-200";
    case "likely_benign": return "bg-teal-50 text-teal-700 border-teal-200";
    case "benign": return "bg-teal-100 text-teal-800 border-teal-200";
  }
}

export function classificationLabel(level: ClassificationLevel): string {
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
