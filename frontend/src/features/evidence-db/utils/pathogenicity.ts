import type { ClassificationLevel } from "../types/variantDb";

/** Map a classification string to a severity level */
export function classifyLevel(classification?: string | null): ClassificationLevel {
  const lower = (classification ?? "").toLowerCase().trim();
  if (!lower || lower === "not specified" || lower === "unknown") return "uncertain";

  // Pathogenic
  if (lower === "pathogenic" || lower.includes("pathogenic") && !lower.includes("likely") && !lower.includes("benign")) {
    return "pathogenic";
  }
  if (lower.includes("likely pathogenic") || lower === "lp") return "likely_pathogenic";

  // Benign
  if (lower === "benign" || lower.includes("benign") && !lower.includes("likely") && !lower.includes("pathogenic")) {
    return "benign";
  }
  if (lower.includes("likely benign") || lower === "lb") return "likely_benign";

  // VUS and everything else
  if (lower.includes("uncertain") || lower.includes("vus") || lower.includes("conflicting")) return "uncertain";

  return "uncertain";
}

/** Severity ordering — lower index = more severe */
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

/** Pick the "worst" (most severe) classification from a list */
export function worstClassification(levels: ClassificationLevel[]): ClassificationLevel {
  if (levels.length === 0) return "uncertain";
  return levels.reduce((worst, current) =>
    severityRank(current) < severityRank(worst) ? current : worst,
  );
}

/**
 * CSS color for a classification level — Helix dark theme.
 * Luminous colors designed to pop against #0a0e17 background.
 */
export function classificationColor(level: ClassificationLevel): string {
  switch (level) {
    case "pathogenic": return "#FF4D6D";
    case "likely_pathogenic": return "#FF7849";
    case "uncertain": return "#FFB323";
    case "likely_benign": return "#4ECDC4";
    case "benign": return "#2DD4BF";
  }
}

/** Glow color (rgba) for a classification level — for shadows and backgrounds */
export function classificationGlow(level: ClassificationLevel): string {
  switch (level) {
    case "pathogenic": return "rgba(255, 77, 109, 0.15)";
    case "likely_pathogenic": return "rgba(255, 120, 73, 0.15)";
    case "uncertain": return "rgba(255, 179, 35, 0.12)";
    case "likely_benign": return "rgba(78, 205, 196, 0.12)";
    case "benign": return "rgba(45, 212, 191, 0.12)";
  }
}

/**
 * Inline style object for a classification badge — dark theme.
 * Returns CSS properties for background, border, and text color.
 */
export function classificationBadgeStyle(level: ClassificationLevel): React.CSSProperties {
  const hex = classificationColor(level);
  return {
    backgroundColor: `${hex}1a`,
    borderColor: `${hex}40`,
    color: hex,
  };
}

/** Human-readable label for a classification level */
export function classificationLabel(level: ClassificationLevel): string {
  switch (level) {
    case "pathogenic": return "Pathogenic";
    case "likely_pathogenic": return "Likely Pathogenic";
    case "uncertain": return "VUS";
    case "likely_benign": return "Likely Benign";
    case "benign": return "Benign";
  }
}

/** Short abbreviated label */
export function classificationShortLabel(level: ClassificationLevel): string {
  switch (level) {
    case "pathogenic": return "P";
    case "likely_pathogenic": return "LP";
    case "uncertain": return "VUS";
    case "likely_benign": return "LB";
    case "benign": return "B";
  }
}
