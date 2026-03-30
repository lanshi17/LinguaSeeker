import type { EvidenceSegment, EvidenceViewModel } from '../types/evidence';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asString(value: unknown) {
  return typeof value === 'string' ? value : null;
}

function splitParagraphs(text: string) {
  return text
    .split(/\n\s*\n/g)
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

function normalizeSegmentsFromArray(arr: unknown[]): EvidenceSegment[] | null {
  const segments: EvidenceSegment[] = [];
  for (let i = 0; i < arr.length; i += 1) {
    const item = arr[i];
    if (!isRecord(item)) return null;

    const sourceText = asString(item.sourceText) ?? asString(item.source_text) ?? asString(item.source) ?? '';
    const targetText =
      asString(item.targetText) ??
      asString(item.target_text) ??
      asString(item.translatedText) ??
      asString(item.translated_text) ??
      asString(item.translation) ??
      '';

    if (sourceText.length === 0 && targetText.length === 0) return null;

    const id = asString(item.id) ?? `seg_${i}`;
    const groupId = asString(item.groupId) ?? asString(item.group_id) ?? undefined;
    segments.push({ id, sourceText, targetText, groupId });
  }
  return segments;
}

export function normalizeEvidence(data: unknown): EvidenceViewModel {
  if (!isRecord(data)) {
    return {
      sourceLang: 'en',
      targetLang: 'zh',
      segments: [],
      raw: data,
      warning: 'Unsupported evidence format'
    };
  }

  const sourceLang = asString(data.sourceLang) ?? asString(data.source_lang) ?? 'en';
  const targetLang = asString(data.targetLang) ?? asString(data.target_lang) ?? 'zh';

  const segmentsRaw = data.segments;
  if (Array.isArray(segmentsRaw)) {
    const segs = normalizeSegmentsFromArray(segmentsRaw);
    if (segs) {
      return { sourceLang, targetLang, segments: segs, raw: data };
    }
  }

  const sourceText =
    asString(data.source_text) ?? asString(data.sourceText) ?? asString(data.source) ?? asString(data.text_source);
  const targetText =
    asString(data.translated_text) ??
    asString(data.translatedText) ??
    asString(data.target_text) ??
    asString(data.targetText) ??
    asString(data.translation);

  if (sourceText || targetText) {
    const sourceParts = sourceText ? splitParagraphs(sourceText) : [];
    const targetParts = targetText ? splitParagraphs(targetText) : [];
    const maxLen = Math.max(sourceParts.length, targetParts.length);
    const segments: EvidenceSegment[] = [];
    for (let i = 0; i < maxLen; i += 1) {
      segments.push({
        id: `p_${i}`,
        sourceText: sourceParts[i] ?? '',
        targetText: targetParts[i] ?? ''
      });
    }
    return {
      sourceLang,
      targetLang,
      segments,
      raw: data,
      warning: 'Highlighting is unavailable for this evidence payload'
    };
  }

  return {
    sourceLang,
    targetLang,
    segments: [],
    raw: data,
    warning: 'Unsupported evidence format'
  };
}
