import type {
  ContentBlock,
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

/** Multilingual aliases for common evidence terms. Non-English source
 *  documents use localised spellings for disease names and variant types;
 *  without these aliases the highlight search (which keys on the English
 *  standardised value) misses every occurrence in the original language.
 *  Keys are lower-cased English values; values are translated surface
 *  forms. Only include aliases that are specific enough to avoid false
 *  positives (e.g. "причин" matches the common Russian word "по причине"). */
const EVIDENCE_ALIASES: Record<string, string[]> = {
  // Disease names
  "rett syndrome": ["синдром ретта", "синдромом ретта", "синдрому ретта", "ретт", "rett综合征", "rett症候群", "rett 증후군", "레트 증후군"],
  // Variant types / consequences — specific biomedical terms only
  missense: ["миссенс"],
  "missense_variant": ["миссенс"],
  frameshift: ["сдвиг рамки", "frameshift"],
  "frameshift mutation": ["сдвиг рамки"],
  nonsense: ["нонсенс"],
  "stop_gained": ["нонсенс"],
  "de novo": ["de novo"],
};

/** Extract searchable sub-entities from a long evidence value. Long values
 *  (e.g. "c.468C>G (p.D156E) in MECP2, heterozygous") are composite
 *  descriptions whose individual parts (HGVS notation, gene symbols,
 *  parenthesised content, comma-separated phrases) can be matched
 *  independently in the document text even when the full sentence cannot.
 *  Only invoked for values longer than 30 chars; output is capped to avoid
 *  combinatorial blow-up. */
const STOP_WORDS = new Set(["THE", "AND", "FOR", "NOT", "BUT", "WITH", "PRO", "IN", "AT", "ON", "OF", "TO", "AS", "BY", "AN", "OR"]);
function extractSubEntities(value: string): string[] {
  // Short values are searched as-is; no need to break them down.
  if (value.length <= 30) return [];
  const entities: string[] = [];
  // HGVS notation: c.468C>G (missense), p.R168X (stop-gain), p.D156E, c.913insT, etc.
  entities.push(...(value.match(/[cp]\.\d+[ACGT]>[ACGT][ACGT]?|[cp]\.\d+[A-Z]\d*[A-Z]|c\.\d+ins[A-Z]+/gi) || []));
  // Gene symbols: all-caps words 3–8 chars, excluding stop words
  entities.push(...((value.match(/\b[A-Z]{3,8}\b/g) || []).filter((g) => !STOP_WORDS.has(g))));
  // Parenthesised content (e.g. "p.D156E" from "c.468C>G (p.D156E)")
  entities.push(...(value.match(/\(([^)]+)\)/g) || []).map((p) => p.slice(1, -1).trim()));
  // Comma / semicolon separated phrases (e.g. "c.913insT" from "frameshift, c.913insT")
  for (const part of value.split(/[,;]/).map((s) => s.trim())) {
    if (part.length >= 3 && part.length <= 40 && part !== value.trim()) entities.push(part);
  }
  return [...new Set(entities)].filter((e) => e.length >= 3).slice(0, 12);
}

/** Generate search-term variants for an evidence value so it can be matched
 *  in non-English source text:
 *  1. HGVS notation uses Latin `c.`/`p.` prefixes, but Russian documents
 *     often render them with look-alike Cyrillic `с.`/`р.`. We also strip
 *     HGVS prefixes to match bare mutation strings (e.g. "468C>G" when the
 *     source writes "с.468C>G").
 *  2. Curated multilingual aliases for disease names and variant types
 *     that are commonly localised in source documents.
 *  3. Sub-entity extraction for long values — breaks composite sentences
 *     into individually matchable fragments. */
function expandSearchTerms(value: string): string[] {
  const v = value.trim();
  const terms = [v];
  // HGVS prefix variants: Latin c./p. ↔ Cyrillic с./р.
  const hgvs = v.match(/^([cp])\.(.+)/i);
  if (hgvs) {
    const prefix = hgvs[1].toLowerCase();
    const rest = hgvs[2];
    const cyrillic = prefix === "c" ? "с" : "р";
    terms.push(`${cyrillic}.${rest}`);
    terms.push(rest); // bare mutation without prefix
  }
  // Multilingual aliases for localised disease names / variant types
  const aliases = EVIDENCE_ALIASES[v.toLowerCase()];
  if (aliases) terms.push(...aliases);
  // Sub-entity extraction for long composite values
  terms.push(...extractSubEntities(v));
  return [...new Set(terms)];
}

/** Check if a search term is HGVS notation (c.XXX or p.XXX). Such terms
 *  often appear in source text with inserted spaces (e.g. "c.502 C>T" vs
 *  "c.502C>T"), so we match them with flexible whitespace. */
function isHgvsTerm(term: string): boolean {
  return /^[cp]\.\d+/i.test(term);
}

/** Find ALL case-insensitive occurrences of any of `searchTerms` in `text`.
 *  Returns start/end offset pairs into the original `text`, deduplicated so
 *  that when a short term (e.g. "ретт") is a substring of a longer alias
 *  (e.g. "синдром ретта") only the longer match is kept. Longer matches are
 *  sorted first so they claim their range before shorter substrings.
 *  HGVS terms are matched with flexible whitespace to handle spacing
 *  variants in the source text (e.g. "c.502 C>T" matching "c.502C>T"). */
function findAllOccurrences(text: string, searchTerms: string[]): Array<{ start: number; end: number }> {
  const raw: Array<{ start: number; end: number; len: number }> = [];
  const normalizedText = normalizeForLocation(text);
  for (const rawTerm of searchTerms) {
    const needle = rawTerm.trim();
    if (needle.length < 3) continue;
    if (isHgvsTerm(needle)) {
      // Build a whitespace-flexible regex for HGVS notation.
      // Escape regex special chars, then replace literal spaces with \s*.
      const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s*");
      const re = new RegExp(escaped, "gi");
      let m: RegExpExecArray | null;
      while ((m = re.exec(text)) !== null) {
        raw.push({ start: m.index, end: m.index + m[0].length, len: m[0].length });
        if (m.index === re.lastIndex) re.lastIndex++;
      }
    } else {
      const normalizedNeedle = normalizeForLocation(needle).normalized;
      if (normalizedNeedle.length < 3) continue;
      let idx = 0;
      while ((idx = normalizedText.normalized.indexOf(normalizedNeedle, idx)) >= 0) {
        const start = normalizedBoundaryToOriginalBoundary(
          normalizedText.normalizedToOriginal,
          idx,
          text.length,
        );
        const end = normalizedBoundaryToOriginalBoundary(
          normalizedText.normalizedToOriginal,
          idx + normalizedNeedle.length,
          text.length,
        );
        raw.push({ start, end, len: end - start });
        idx += normalizedNeedle.length;
      }
    }
  }
  // Sort by length desc so longer matches claim ranges first, then by start.
  raw.sort((a, b) => b.len - a.len || a.start - b.start);
  const positions: Array<{ start: number; end: number }> = [];
  for (const r of raw) {
    if (positions.some((p) => r.start < p.end && r.end > p.start)) continue;
    positions.push({ start: r.start, end: r.end });
  }
  return positions;
}

function normalizeCharForLocation(char: string): string {
  return char
    .normalize("NFKC")
    .replace(/[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]/g, "-")
    .replace(/[。｡]/g, ".")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase();
}

function normalizeForLocation(text: string): {
  normalized: string;
  normalizedToOriginal: number[];
} {
  let normalized = "";
  const normalizedToOriginal: number[] = [];
  let previousWasSpace = false;

  for (let index = 0; index < text.length;) {
    const codePoint = text.codePointAt(index);
    if (codePoint === undefined) break;

    const originalIndex = index;
    const rawChar = String.fromCodePoint(codePoint);
    index += rawChar.length;

    const normalizedChar = normalizeCharForLocation(rawChar);
    for (const char of normalizedChar) {
      if (/\s/.test(char)) {
        if (!previousWasSpace) {
          normalized += " ";
          normalizedToOriginal.push(originalIndex);
          previousWasSpace = true;
        }
        continue;
      }
      normalized += char;
      normalizedToOriginal.push(originalIndex);
      previousWasSpace = false;
    }
  }

  while (normalized.startsWith(" ")) {
    normalized = normalized.slice(1);
    normalizedToOriginal.shift();
  }
  while (normalized.endsWith(" ")) {
    normalized = normalized.slice(0, -1);
    normalizedToOriginal.pop();
  }

  return { normalized, normalizedToOriginal };
}

function originalOffsetToNormalizedBoundary(
  normalizedToOriginal: number[],
  originalOffset: number,
): number {
  const index = normalizedToOriginal.findIndex((mappedOffset) => mappedOffset >= originalOffset);
  return index >= 0 ? index : normalizedToOriginal.length;
}

function normalizedBoundaryToOriginalBoundary(
  normalizedToOriginal: number[],
  normalizedOffset: number,
  originalLength: number,
): number {
  if (normalizedOffset >= normalizedToOriginal.length) return originalLength;
  return normalizedToOriginal[Math.max(0, normalizedOffset)];
}

function locateTraceRangeInFullText(
  fullText: string,
  highlight?: EvidenceChainHighlight | null,
): { start: number; end: number } | null {
  if (!highlight?.text.trim()) return null;
  const range = clampHighlight(highlight);
  if (range.end <= range.start) return null;

  const full = normalizeForLocation(fullText);
  const sentence = normalizeForLocation(highlight.text.trim());
  const sentenceStart = full.normalized.indexOf(sentence.normalized);
  if (sentenceStart < 0) return null;

  const normalizedRangeStart = originalOffsetToNormalizedBoundary(
    sentence.normalizedToOriginal,
    range.start,
  );
  const normalizedRangeEnd = originalOffsetToNormalizedBoundary(
    sentence.normalizedToOriginal,
    range.end,
  );

  return {
    start: normalizedBoundaryToOriginalBoundary(
      full.normalizedToOriginal,
      sentenceStart + normalizedRangeStart,
      fullText.length,
    ),
    end: normalizedBoundaryToOriginalBoundary(
      full.normalizedToOriginal,
      sentenceStart + normalizedRangeEnd,
      fullText.length,
    ),
  };
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
  trace: EvidenceTrackTrace | undefined,
  track: "original" | "translated",
) {
  if (!trace) return null;
  return track === "original" ? trace.original : trace.translated;
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

    // Evidence values of any length are searched in the full text. Short
    // values (gene symbols, HGVS variants) are processed first so a longer
    // phrase containing them does not shadow the entity match; sub-entity
    // extraction (in expandSearchTerms) lets long composite values match
    // their individual parts. Occupied ranges prevent overlap.
    const MAX_VALUE_LEN = 200;
    const valuedItems = detail.items
      .filter((item) => {
        const v = item.value?.trim();
        return v && v.length >= 3 && v.length <= MAX_VALUE_LEN;
      })
      .sort((a, b) => (a.value!.length) - (b.value!.length));

    const occupied: Array<{ start: number; end: number }> = [];

    for (const item of valuedItems) {
      const tone = evidenceToneForItem(item);
      if (!enabledTones.has(tone)) continue;
      const cat = categoryFromItem(item);
      if (enabledCategories && cat && !enabledCategories.has(cat)) continue;

      // Search every occurrence of the evidence value (and its cross-script
      // trace.original_value when present (it may carry the source-language
      // spelling). We intentionally do NOT use trace.source_span offsets:
      // those mark sentence-length context snippets, not the entity itself.
      const trace = detail.traces.find(
        (t) => t.canonical_evidence_id === item.canonical_evidence_id,
      );
      const trackValue = track === "original" ? trace?.original_value : trace?.translated_value;
      const searchTerms = expandSearchTerms(item.value!);
      if (trackValue && trackValue.trim() && !searchTerms.includes(trackValue.trim())) {
        searchTerms.push(trackValue.trim());
      }
      const positions = findAllOccurrences(fullText, searchTerms);
      let matched = false;
      for (const pos of positions) {
        if (occupied.some((o) => pos.start < o.end && pos.end > o.start)) continue;
        occupied.push(pos);
        matched = true;
        locatedHighlights.push({
          evidenceId: item.canonical_evidence_id,
          fieldId: item.field_id,
          label: item.field_name ?? item.field_id,
          tone,
          category: cat,
          start: pos.start,
          end: pos.end,
          selected: item.canonical_evidence_id === selectedEvidenceId,
        });
      }

      if (!matched) {
        const traceRange = locateTraceRangeInFullText(
          fullText,
          traceHighlightForTrack(trace, track),
        );
        if (
          traceRange &&
          !occupied.some((o) => traceRange.start < o.end && traceRange.end > o.start)
        ) {
          occupied.push(traceRange);
          locatedHighlights.push({
            evidenceId: item.canonical_evidence_id,
            fieldId: item.field_id,
            label: item.field_name ?? item.field_id,
            tone,
            category: cat,
            start: traceRange.start,
            end: traceRange.end,
            selected: item.canonical_evidence_id === selectedEvidenceId,
          });
        }
      }

    }

    return {
      track,
      paragraphs: [
        {
          id: `${track}-full-text`,
          text: fullText,
          highlights: locatedHighlights.sort((a, b) => a.start - b.start),
        },
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

/** Build block-level highlights by searching evidence values in the
 *  concatenated text of structured blocks. Used when trace-based
 *  highlight spans are empty/unavailable — mirrors the fullText search
 *  logic in `buildEvidenceDocument` but maps offsets to the block text
 *  coordinate space (blocks joined with "\n\n" separators). */
export function buildBlockHighlightsFromValues(
  blocks: ContentBlock[],
  detail: EvidenceGroupDetailResponse,
  track: "original" | "translated",
  selectedEvidenceId?: string | null,
  enabledCategories?: ReadonlySet<string> | null,
): Array<{
  evidenceId: string;
  fieldId: string;
  label: string;
  tone: EvidenceHighlightTone;
  category?: string | null;
  globalStart: number;
  globalEnd: number;
  selected: boolean;
}> {
  // Build concatenated text matching StructuredBlockRenderer's buildBlockRanges
  let fullText = "";
  for (const block of blocks) {
    let text = "";
    switch (block.type) {
      case "table":
        text = [
          ...(block.table_caption ?? []),
          block.text ?? "",
          ...(block.table_footnote ?? []),
        ].filter(Boolean).join("\n");
        break;
      case "list":
        text = (block.list_items ?? []).join("\n");
        break;
      case "image":
      case "chart":
        text = [
          ...(block.image_caption ?? block.chart_caption ?? []),
          block.content ?? "",
          ...(block.image_footnote ?? block.chart_footnote ?? []),
        ].filter(Boolean).join("\n");
        break;
      default:
        text = block.text ?? "";
    }
    if (text) {
      fullText += text + "\n\n";
    }
  }
  if (!fullText) return [];

  const highlights: Array<{
    evidenceId: string;
    fieldId: string;
    label: string;
    tone: EvidenceHighlightTone;
    category?: string | null;
    globalStart: number;
    globalEnd: number;
    selected: boolean;
  }> = [];

  const MAX_VALUE_LEN = 200;
  const valuedItems = detail.items
    .filter((item) => {
      const v = item.value?.trim();
      return v && v.length >= 3 && v.length <= MAX_VALUE_LEN;
    })
    .sort((a, b) => (a.value!.length) - (b.value!.length));

  const occupied: Array<{ start: number; end: number }> = [];

  for (const item of valuedItems) {
    const tone = evidenceToneForItem(item);
    const cat = categoryFromItem(item);
    if (enabledCategories && cat && !enabledCategories.has(cat)) continue;

    const tr = detail.traces.find(
      (t) => t.canonical_evidence_id === item.canonical_evidence_id,
    );
    const trackValue = track === "original" ? tr?.original_value : tr?.translated_value;
    const searchTerms = expandSearchTerms(item.value!);
    if (trackValue && trackValue.trim() && !searchTerms.includes(trackValue.trim())) {
      searchTerms.push(trackValue.trim());
    }
    const positions = findAllOccurrences(fullText, searchTerms);
    for (const pos of positions) {
      if (occupied.some((o) => pos.start < o.end && pos.end > o.start)) continue;
      occupied.push(pos);
      highlights.push({
        evidenceId: item.canonical_evidence_id,
        fieldId: item.field_id,
        label: item.field_name ?? item.field_id,
        tone,
        category: cat,
        globalStart: pos.start,
        globalEnd: pos.end,
        selected: item.canonical_evidence_id === selectedEvidenceId,
      });
    }
  }

  return highlights;
}
