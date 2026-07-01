import type {
  ContentBlock,
  EvidenceGroupDetailResponse,
  TranslationSpanPair,
} from "../types/evidenceSearch";
import type { EvidenceDocument } from "./evidenceDocument";

export interface AlignmentInteractionState {
  hoveredPairId: string | null;
  pinnedPairId: string | null;
}

export interface AlignmentTextHighlight {
  pairId: string;
  start: number;
  end: number;
  active: boolean;
  pinned: boolean;
  confidence: number;
  method: TranslationSpanPair["method"];
}

export type AlignmentHighlightMap = Record<string, AlignmentTextHighlight[]>;

export function activeAlignmentPairId(
  state: AlignmentInteractionState,
): string | null {
  return state.hoveredPairId ?? state.pinnedPairId;
}

export function buildAlignmentHighlights(
  detail: EvidenceGroupDetailResponse,
  track: "original" | "translated",
  text: string,
  state: AlignmentInteractionState,
): AlignmentTextHighlight[] {
  const activePairId = activeAlignmentPairId(state);
  const pairs = (detail.translation_alignment ?? [])
    .flatMap((chunk) => chunk.span_pairs ?? [])
    .sort((a, b) => trackStartOffset(a, track) - trackStartOffset(b, track));
  const highlights: AlignmentTextHighlight[] = [];
  let cursor = 0;

  for (const pair of pairs) {
    const pairText = trackText(pair, track).trim();
    if (!pairText) {
      continue;
    }

    const range = locatePairRange(text, pairText, trackStartOffset(pair, track), trackEndOffset(pair, track), cursor);
    if (!range) {
      continue;
    }

    const overlaps = highlights.some(
      (highlight) => range.start < highlight.end && range.end > highlight.start,
    );
    if (overlaps) {
      continue;
    }

    highlights.push({
      pairId: pair.pair_id,
      start: range.start,
      end: range.end,
      active: pair.pair_id === activePairId,
      pinned: pair.pair_id === state.pinnedPairId,
      confidence: pair.confidence,
      method: pair.method,
    });
    cursor = range.end;
  }

  return highlights;
}

export function buildAlignmentHighlightMap(
  detail: EvidenceGroupDetailResponse,
  document: EvidenceDocument,
  track: "original" | "translated",
  state: AlignmentInteractionState,
): AlignmentHighlightMap {
  return Object.fromEntries(
    document.paragraphs.map((paragraph) => [
      paragraph.id,
      buildAlignmentHighlights(detail, track, paragraph.text, state),
    ]),
  );
}

export function buildAlignmentHighlightsForBlocks(
  blocks: ContentBlock[] | null | undefined,
  detail: EvidenceGroupDetailResponse,
  track: "original" | "translated",
  state: AlignmentInteractionState,
): AlignmentTextHighlight[] {
  const text = contentBlocksText(blocks);
  if (!text) {
    return [];
  }
  return buildAlignmentHighlights(detail, track, text, state);
}

function contentBlocksText(blocks: ContentBlock[] | null | undefined): string {
  let text = "";
  for (const block of blocks ?? []) {
    const blockText = contentBlockText(block);
    if (blockText) {
      text += `${blockText}\n\n`;
    }
  }
  return text;
}

function contentBlockText(block: ContentBlock): string {
  switch (block.type) {
    case "table":
      return [
        ...(block.table_caption ?? []),
        block.text ?? "",
        ...(block.table_footnote ?? []),
      ].filter(Boolean).join("\n");
    case "list":
      return (block.list_items ?? []).join("\n");
    case "code":
      return [
        ...(block.code_caption ?? []),
        block.code_body ?? "",
      ].filter(Boolean).join("\n");
    case "image":
    case "chart":
      return [
        ...(block.image_caption ?? block.chart_caption ?? []),
        block.content ?? "",
        ...(block.image_footnote ?? block.chart_footnote ?? []),
      ].filter(Boolean).join("\n");
    default:
      return block.text ?? "";
  }
}

function trackText(pair: TranslationSpanPair, track: "original" | "translated"): string {
  return track === "original" ? pair.original_text : pair.english_text;
}

function trackStartOffset(pair: TranslationSpanPair, track: "original" | "translated"): number {
  return track === "original" ? pair.original_start_offset : pair.english_start_offset;
}

function trackEndOffset(pair: TranslationSpanPair, track: "original" | "translated"): number {
  return track === "original" ? pair.original_end_offset : pair.english_end_offset;
}

function locatePairRange(
  text: string,
  pairText: string,
  expectedStart: number,
  expectedEnd: number,
  cursor: number,
): { start: number; end: number } | null {
  if (
    expectedStart >= 0 &&
    expectedEnd > expectedStart &&
    expectedEnd <= text.length &&
    text.slice(expectedStart, expectedEnd) === pairText
  ) {
    return { start: expectedStart, end: expectedEnd };
  }

  const monotonicStart = text.indexOf(pairText, Math.max(0, cursor));
  const start = monotonicStart >= 0 ? monotonicStart : text.indexOf(pairText);
  if (start < 0) {
    return null;
  }
  return { start, end: start + pairText.length };
}
