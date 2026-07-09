import { formatDate as formatAppDate } from "@/lib/utils/format";
import type { LiteratureEvidenceRow } from "./literatureRows";

export function formatEvidencePercent(value?: number | null): string {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

export function formatEvidenceDate(isoString?: string | null): string {
  return formatAppDate(isoString, "zh-CN");
}

export function joinedLabel(values: string[]): string {
  return values.length > 0 ? values.join(", ") : "\u2014";
}

export function literatureTitle(
  row: LiteratureEvidenceRow,
  t: (key: string) => string,
): string {
  return row.title?.trim() || t("evidence.col.untitled");
}
