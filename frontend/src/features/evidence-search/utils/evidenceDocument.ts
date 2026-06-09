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
  start: number;
  end: number;
  selected: boolean;
}

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

export type EvidenceToneCounts = Record<EvidenceHighlightTone, number>;

const EMPTY_TONE_COUNTS: EvidenceToneCounts = {
  classification: 0,
  disease: 0,
  functional: 0,
  gene: 0,
  neutral: 0,
  variant: 0,
};

function categoryFromItem(item: EvidenceGroupItem) {
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

export function countEvidenceHighlightTones(
  items: EvidenceGroupItem[],
): EvidenceToneCounts {
  const counts = { ...EMPTY_TONE_COUNTS };
  for (const item of items) {
    counts[evidenceToneForItem(item)] += 1;
  }
  return counts;
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

function findHighlightInFullText(
  fullText: string,
  highlight: EvidenceChainHighlight,
  value?: string | null,
): { start: number; end: number } | null {
  const valueAnchor = findAnchorValue(fullText, value);
  if (valueAnchor) {
    return valueAnchor;
  }

  const candidates = [highlight.text.slice(highlight.highlight_start, highlight.highlight_end), highlight.text]
    .map((candidate) => candidate?.trim())
    .filter((candidate): candidate is string => Boolean(candidate && candidate.length >= 3));

  for (const candidate of candidates) {
    const index = fullText.indexOf(candidate);
    if (index >= 0) {
      return { start: index, end: index + candidate.length };
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
): EvidenceDocument {
  const items = itemByEvidenceId(detail);
  const fullText = fullTextForTrack(detail, track)?.trim();

  if (fullText) {
    const highlights = detail.traces.flatMap((trace): EvidenceDocumentHighlight[] => {
      const highlight = traceHighlightForTrack(trace, track);
      if (!highlight) {
        return [];
      }

      const item = items.get(trace.canonical_evidence_id);
      const tone = evidenceToneForItem(item);
      if (!enabledTones.has(tone)) {
        return [];
      }

      const range = findHighlightInFullText(
        fullText,
        highlight,
        traceValueForTrack(trace, track),
      );
      if (!range || range.end <= range.start) {
        return [];
      }

      return [{
        evidenceId: trace.canonical_evidence_id,
        fieldId: trace.field_id,
        label: labelForTrace(trace),
        tone,
        start: range.start,
        end: range.end,
        selected: trace.canonical_evidence_id === selectedEvidenceId,
      }];
    });

    return {
      track,
      paragraphs: [{
        id: `${track}-full-text`,
        text: fullText,
        highlights: highlights.sort((a, b) => a.start - b.start),
      }],
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
      const highlights: EvidenceDocumentHighlight[] = [];
      if (enabledTones.has(tone)) {
        const range = clampHighlight(highlight);
        if (range.end > range.start) {
          highlights.push({
            evidenceId: trace.canonical_evidence_id,
            fieldId: trace.field_id,
            label: labelForTrace(trace),
            tone,
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
