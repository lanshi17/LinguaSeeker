import type {
  EvidenceChainHighlight,
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
  EvidenceHighlightTone,
  EvidenceTrackTrace,
} from "../types/evidenceSearch";

export interface EvidenceDocumentHighlight {
  evidenceId: string;
  fieldId: string;
  label: string;
  tone: EvidenceHighlightTone;
  category?: string | null;
  start: number;
  end: number;
  selected: boolean;
}

/**
 * Per-category color palette for the 10 evidence categories (A–J).
 *
 * Each entry contains Tailwind utility strings for:
 * - `chip`: border + bg + text used on pills / layer toggles
 * - `mark`: highlight style used on `<mark>` in the document reader
 */
export const CATEGORY_COLORS: Record<
  string,
  { chip: string; mark: string; label: string; hex: string }
> = {
  A: {
    label: "Variant information",
    hex: "#F59E0B",
    chip: "border-amber-200 bg-amber-50 text-amber-800",
    mark: "bg-amber-200 text-amber-950 ring-1 ring-amber-300",
  },
  B: {
    label: "Case and phenotype",
    hex: "#3B82F6",
    chip: "border-blue-200 bg-blue-50 text-blue-800",
    mark: "bg-blue-200 text-blue-950 ring-1 ring-blue-300",
  },
  C: {
    label: "Segregation",
    hex: "#8B5CF6",
    chip: "border-violet-200 bg-violet-50 text-violet-800",
    mark: "bg-violet-200 text-violet-950 ring-1 ring-violet-300",
  },
  D: {
    label: "Population frequency",
    hex: "#06B6D4",
    chip: "border-cyan-200 bg-cyan-50 text-cyan-800",
    mark: "bg-cyan-200 text-cyan-950 ring-1 ring-cyan-300",
  },
  E: {
    label: "Computational evidence",
    hex: "#10B981",
    chip: "border-emerald-200 bg-emerald-50 text-emerald-800",
    mark: "bg-emerald-200 text-emerald-950 ring-1 ring-emerald-300",
  },
  F: {
    label: "Functional evidence",
    hex: "#22C55E",
    chip: "border-green-200 bg-green-50 text-green-800",
    mark: "bg-green-200 text-green-950 ring-1 ring-green-300",
  },
  G: {
    label: "Case-control evidence",
    hex: "#F97316",
    chip: "border-orange-200 bg-orange-50 text-orange-800",
    mark: "bg-orange-200 text-orange-950 ring-1 ring-orange-300",
  },
  H: {
    label: "Contradiction evidence",
    hex: "#EF4444",
    chip: "border-red-200 bg-red-50 text-red-800",
    mark: "bg-red-200 text-red-950 ring-1 ring-red-300",
  },
  I: {
    label: "Gene function",
    hex: "#14B8A6",
    chip: "border-teal-200 bg-teal-50 text-teal-800",
    mark: "bg-teal-200 text-teal-950 ring-1 ring-teal-300",
  },
  J: {
    label: "Authority and validity",
    hex: "#EC4899",
    chip: "border-pink-200 bg-pink-50 text-pink-800",
    mark: "bg-pink-200 text-pink-950 ring-1 ring-pink-300",
  },
};

/** Ordered list of known category keys. */
export const EVIDENCE_CATEGORIES = Object.keys(CATEGORY_COLORS);

export interface EvidenceDocumentParagraph {
  id: string;
  page?: number | null;
  text: string;
  highlights: EvidenceDocumentHighlight[];
}

export interface EvidenceDocument {
  track: "original" | "translated";
  paragraphs: EvidenceDocumentParagraph[];
}

function categoryFromItem(item?: EvidenceGroupItem | null) {
  if (!item) {
    return null;
  }
  if (item.category) {
    return item.category;
  }
  return item.field_id.includes(".") ? item.field_id.split(".", 1)[0] : null;
}

export function evidenceToneForItem(
  item?: EvidenceGroupItem | null,
): EvidenceHighlightTone {
  const fieldId = item?.field_id.toLowerCase() ?? "";
  const category = item ? categoryFromItem(item) : null;

  if (fieldId.includes("gene")) {
    return "gene";
  }
  if (fieldId.includes("variant") || fieldId.includes("hgvs")) {
    return "variant";
  }
  if (fieldId.includes("disease") || fieldId.includes("phenotype")) {
    return "disease";
  }
  if (
    fieldId.includes("classification") ||
    fieldId.includes("pathogenic") ||
    fieldId.includes("acmg")
  ) {
    return "classification";
  }
  if (["F", "G", "I"].includes(category ?? "")) {
    return "functional";
  }
  return "neutral";
}

/** Count evidence items per category letter (A–J). */
export function countEvidenceCategories(
  items: EvidenceGroupItem[],
): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of items) {
    const cat = categoryFromItem(item);
    if (cat) {
      counts[cat] = (counts[cat] ?? 0) + 1;
    }
  }
  return counts;
}

export function hasTranslatedDocumentText(
  detail: EvidenceGroupDetailResponse,
): boolean {
  return (
    Boolean(detail.translated_document_text?.trim()) ||
    detail.traces.some((trace) => Boolean(trace.translated?.text.trim()))
  );
}

function labelForTrace(trace: EvidenceTrackTrace) {
  return trace.field_name ?? trace.field_id;
}

function clampHighlight(
  highlight: EvidenceChainHighlight,
): { start: number; end: number } {
  const start = Math.max(0, Math.min(highlight.highlight_start, highlight.text.length));
  const end = Math.max(start, Math.min(highlight.highlight_end, highlight.text.length));
  return { start, end };
}

function isSafeAnchorValue(value: string) {
  if (value.length === 1) {
    return false;
  }
  if (value.length === 2) {
    return value === value.toUpperCase();
  }
  return true;
}

function findAnchorValue(text: string, rawValue?: string | null) {
  const value = rawValue?.trim();
  if (!value || !isSafeAnchorValue(value)) {
    return null;
  }
  if (value.length === 2) {
    const match = new RegExp(`(^|[^A-Za-z0-9])(${value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})(?![A-Za-z0-9])`).exec(text);
    if (!match || match.index < 0) {
      return null;
    }
    const start = match.index + match[1].length;
    return { start, end: start + value.length };
  }
  const index = text.toLowerCase().indexOf(value.toLowerCase());
  if (index < 0) {
    return null;
  }
  return { start: index, end: index + value.length };
}

function escapedRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Search for a candidate in text, tolerating whitespace differences. */
function findWithFlexibleWhitespace(
  text: string,
  candidate: string,
): { start: number; end: number } | null {
  const flexible = escapedRegExp(candidate).replace(/\s+/g, "\\s+");
  const match = new RegExp(flexible).exec(text);
  if (match) {
    return { start: match.index, end: match.index + match[0].length };
  }
  return null;
}

function findHighlightInFullText(
  fullText: string,
  highlight: EvidenceChainHighlight,
  value?: string | null,
): { start: number; end: number } | null {
  // 1. Try global offsets from source_span — most reliable when the full
  //    text is the same formatted_text used during extraction.
  const span = highlight.source_span as Record<string, unknown> | undefined;
  const spanStart = typeof span?.start_offset === "number" ? span.start_offset : undefined;
  const spanEnd = typeof span?.end_offset === "number" ? span.end_offset : undefined;
  if (
    spanStart !== undefined &&
    spanEnd !== undefined &&
    spanStart >= 0 &&
    spanEnd <= fullText.length &&
    spanEnd > spanStart
  ) {
    const textAtOffset = fullText.slice(spanStart, spanEnd);
    if (textAtOffset === highlight.text || textAtOffset.trim() === highlight.text.trim()) {
      return { start: spanStart, end: spanEnd };
    }
  }

  // 2. Try value anchor search in the full text.
  const valueAnchor = findAnchorValue(fullText, value);
  if (valueAnchor) {
    return valueAnchor;
  }

  // 3. Try exact snippet text search (marked portion first, then full snippet).
  const candidates = [
    highlight.text.slice(highlight.highlight_start, highlight.highlight_end),
    highlight.text,
  ]
    .map((candidate) => candidate?.trim())
    .filter((candidate): candidate is string => Boolean(candidate && candidate.length >= 3));

  for (const candidate of candidates) {
    const index = fullText.indexOf(candidate);
    if (index >= 0) {
      return { start: index, end: index + candidate.length };
    }
  }

  // 4. Fallback: flexible whitespace search (snippet may differ from full
  //    text in line breaks / spacing).
  for (const candidate of candidates) {
    const result = findWithFlexibleWhitespace(fullText, candidate);
    if (result) {
      return result;
    }
  }

  return null;
}

function fullTextForTrack(
  detail: EvidenceGroupDetailResponse,
  track: "original" | "translated",
) {
  return track === "original"
    ? detail.original_document_text
    : detail.translated_document_text;
}

function traceHighlightForTrack(
  trace: EvidenceTrackTrace,
  track: "original" | "translated",
) {
  return track === "original" ? trace.original : trace.translated;
}

function traceValueForTrack(
  trace: EvidenceTrackTrace,
  track: "original" | "translated",
) {
  return track === "original" ? trace.original_value : trace.translated_value;
}

function itemByEvidenceId(detail: EvidenceGroupDetailResponse) {
  return new Map(
    detail.items.map((item) => [item.canonical_evidence_id, item] as const),
  );
}

export function buildEvidenceDocument(
  detail: EvidenceGroupDetailResponse,
  track: "original" | "translated",
  enabledTones: ReadonlySet<EvidenceHighlightTone> = new Set([
    "classification",
    "disease",
    "functional",
    "gene",
    "neutral",
    "variant",
  ]),
  selectedEvidenceId?: string | null,
  enabledCategories?: ReadonlySet<string> | null,
): EvidenceDocument {
  const items = itemByEvidenceId(detail);
  const fullText = fullTextForTrack(detail, track)?.trim();

  if (fullText) {
    const locatedHighlights: EvidenceDocumentHighlight[] = [];
    const snippetParagraphs: EvidenceDocumentParagraph[] = [];

    detail.traces.forEach((trace, index) => {
      const highlight = traceHighlightForTrack(trace, track);
      if (!highlight) {
        return;
      }

      const item = items.get(trace.canonical_evidence_id);
      const tone = evidenceToneForItem(item);
      if (!enabledTones.has(tone)) {
        return;
      }
      const cat = categoryFromItem(item);
      if (enabledCategories && cat && !enabledCategories.has(cat)) {
        return;
      }

      const range = findHighlightInFullText(
        fullText,
        highlight,
        traceValueForTrack(trace, track),
      );

      if (range && range.end > range.start) {
        locatedHighlights.push({
          evidenceId: trace.canonical_evidence_id,
          fieldId: trace.field_id,
          label: labelForTrace(trace),
          tone,
          category: cat,
          start: range.start,
          end: range.end,
          selected: trace.canonical_evidence_id === selectedEvidenceId,
        });
      } else if (highlight.text) {
        // Could not locate in the full text — show the snippet as a
        // separate paragraph so the evidence is still visible.
        const snippetRange = clampHighlight(highlight);
        const snippetHighlights: EvidenceDocumentHighlight[] = [];
        if (snippetRange.end > snippetRange.start) {
          snippetHighlights.push({
            evidenceId: trace.canonical_evidence_id,
            fieldId: trace.field_id,
            label: labelForTrace(trace),
            tone,
            category: cat,
            start: snippetRange.start,
            end: snippetRange.end,
            selected: trace.canonical_evidence_id === selectedEvidenceId,
          });
        }
        snippetParagraphs.push({
          id: `${track}-${trace.canonical_evidence_id}-${index}`,
          page: highlight.page,
          text: highlight.text,
          highlights: snippetHighlights,
        });
      }
    });

    return {
      track,
      paragraphs: [
        {
          id: `${track}-full-text`,
          text: fullText,
          highlights: locatedHighlights.sort((a, b) => a.start - b.start),
        },
        ...snippetParagraphs,
      ],
    };
  }

  return {
    track,
    paragraphs: detail.traces.flatMap((trace, index): EvidenceDocumentParagraph[] => {
      const highlight = traceHighlightForTrack(trace, track);
      if (!highlight?.text) {
        return [];
      }

      const item = items.get(trace.canonical_evidence_id);
      const tone = evidenceToneForItem(item);
      const cat = categoryFromItem(item);
      const highlights: EvidenceDocumentHighlight[] = [];
      if (enabledTones.has(tone) && (!enabledCategories || !cat || enabledCategories.has(cat))) {
        const range = clampHighlight(highlight);
        if (range.end > range.start) {
          highlights.push({
            evidenceId: trace.canonical_evidence_id,
            fieldId: trace.field_id,
            label: labelForTrace(trace),
            tone,
            category: categoryFromItem(item),
            start: range.start,
            end: range.end,
            selected: trace.canonical_evidence_id === selectedEvidenceId,
          });
        }
      }

      return [{
        id: `${track}-${trace.canonical_evidence_id}-${index}`,
        page: highlight.page,
        text: highlight.text,
        highlights,
      }];
    }),
  };
}
