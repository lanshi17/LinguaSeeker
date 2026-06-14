import { CATEGORY_COLORS } from "./evidenceDocument";

/** Chip styles keyed by category letter, falling back to gray styles. */
export function categoryChipStyle(category?: string | null): string {
  if (category && CATEGORY_COLORS[category]) {
    return CATEGORY_COLORS[category].chip;
  }
  return "border-gray-200 bg-gray-50 text-gray-700";
}

/** Mark/highlight styles keyed by category letter, falling back to neutral. */
export function categoryMarkStyle(category?: string | null): string {
  if (category && CATEGORY_COLORS[category]) {
    return CATEGORY_COLORS[category].mark;
  }
  return "bg-gray-200 text-gray-950 ring-1 ring-gray-300";
}

const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(CATEGORY_COLORS).map(([k, v]) => [k, v.label]),
);

export function categoryLabel(category?: string | null) {
  if (!category) {
    return "Uncategorized";
  }
  return CATEGORY_LABELS[category] ?? category;
}
