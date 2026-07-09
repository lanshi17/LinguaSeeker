import type {
  AnnotationTrack,
  UserAnnotation,
} from "../types/annotations";
import type {
  EvidenceChainHighlight,
  EvidenceGroupDetailResponse,
  EvidenceTrackTrace,
  TranslationSpanPair,
} from "../types/evidenceSearch";

const MIRRORED_ANNOTATION_ID_PREFIX = "mirrored:";

interface AnnotationRange {
  start: number;
  end: number;
}

interface MirroredAnnotationTarget {
  track: AnnotationTrack;
  paragraphId: string;
  range: AnnotationRange;
}

export function sourceAnnotationIdForMutation(annotationId: string): string {
  if (!annotationId.startsWith(MIRRORED_ANNOTATION_ID_PREFIX)) {
    return annotationId;
  }
  return annotationId.slice(MIRRORED_ANNOTATION_ID_PREFIX.length).split(":")[0] ?? annotationId;
}

export function buildSynchronizedAnnotations(
  detail: EvidenceGroupDetailResponse,
  annotations: UserAnnotation[],
): UserAnnotation[] {
  const mirrored = annotations.flatMap((annotation) => {
    const target = mirroredAnnotationTarget(detail, annotation);
    if (!target || hasExactAnnotation(annotations, target)) {
      return [];
    }
    return [{
      ...annotation,
      id: mirroredAnnotationId(annotation.id, target.track),
      track: target.track,
      paragraph_id: target.paragraphId,
      start_offset: target.range.start,
      end_offset: target.range.end,
    }];
  });

  return [...annotations, ...mirrored].sort(
    (left, right) =>
      left.created_at.localeCompare(right.created_at) ||
      left.id.localeCompare(right.id),
  );
}

function mirroredAnnotationId(sourceAnnotationId: string, track: AnnotationTrack): string {
  return `${MIRRORED_ANNOTATION_ID_PREFIX}${sourceAnnotationId}:${track}`;
}

function mirroredAnnotationTarget(
  detail: EvidenceGroupDetailResponse,
  annotation: UserAnnotation,
): MirroredAnnotationTarget | null {
  const targetTrack = oppositeTrack(annotation.track);
  const paragraphId = mirroredParagraphId(annotation.paragraph_id, annotation.track);
  if (!paragraphId) {
    return null;
  }

  const snippetTarget = snippetMirrorTarget(detail, annotation, targetTrack);
  if (snippetTarget) {
    return snippetTarget;
  }

  const range = alignmentMirrorRange(detail, annotation, targetTrack);
  if (!range) {
    return null;
  }

  return {
    track: targetTrack,
    paragraphId,
    range,
  };
}

function oppositeTrack(track: AnnotationTrack): AnnotationTrack {
  return track === "original" ? "translated" : "original";
}

function mirroredParagraphId(
  paragraphId: string,
  sourceTrack: AnnotationTrack,
): string | null {
  if (!paragraphId.startsWith(`${sourceTrack}-`)) {
    return null;
  }
  return `${oppositeTrack(sourceTrack)}-${paragraphId.slice(sourceTrack.length + 1)}`;
}

function snippetMirrorTarget(
  detail: EvidenceGroupDetailResponse,
  annotation: UserAnnotation,
  targetTrack: AnnotationTrack,
): MirroredAnnotationTarget | null {
  const match = annotation.paragraph_id.match(
    new RegExp(`^${annotation.track}-(.+)-(\\d+)$`),
  );
  if (!match?.[1] || !match[2]) {
    return null;
  }
  const evidenceId = match[1];
  const index = match[2];
  const trace = detail.traces.find(
    (item) => item.canonical_evidence_id === evidenceId,
  );
  if (!trace) {
    return null;
  }

  const sourceHighlight = traceHighlight(trace, annotation.track);
  const targetHighlight = traceHighlight(trace, targetTrack);
  if (!sourceHighlight || !targetHighlight) {
    return null;
  }

  const range = proportionalMirrorRange(annotation, sourceHighlight, targetHighlight);
  if (!range) {
    return null;
  }

  return {
    track: targetTrack,
    paragraphId: `${targetTrack}-${evidenceId}-${index}`,
    range,
  };
}

function traceHighlight(
  trace: EvidenceTrackTrace,
  track: AnnotationTrack,
): EvidenceChainHighlight | null | undefined {
  return track === "original" ? trace.original : trace.translated;
}

function proportionalMirrorRange(
  annotation: UserAnnotation,
  sourceHighlight: EvidenceChainHighlight,
  targetHighlight: EvidenceChainHighlight,
): AnnotationRange | null {
  const sourceRange = highlightRange(sourceHighlight);
  const targetRange = highlightRange(targetHighlight);
  if (!sourceRange || !targetRange || !rangesOverlap(annotationRange(annotation), sourceRange)) {
    return null;
  }

  const sourceLength = sourceRange.end - sourceRange.start;
  const targetLength = targetRange.end - targetRange.start;
  if (sourceLength <= 0 || targetLength <= 0) {
    return null;
  }

  const relativeStart = clamp01((annotation.start_offset - sourceRange.start) / sourceLength);
  const relativeEnd = clamp01((annotation.end_offset - sourceRange.start) / sourceLength);
  const start = targetRange.start + Math.floor(relativeStart * targetLength);
  const end = targetRange.start + Math.ceil(relativeEnd * targetLength);
  return normalizedRange(start, end, targetRange.end);
}

function highlightRange(highlight: EvidenceChainHighlight): AnnotationRange | null {
  return normalizedRange(
    highlight.highlight_start,
    highlight.highlight_end,
    highlight.text.length,
  );
}

function alignmentMirrorRange(
  detail: EvidenceGroupDetailResponse,
  annotation: UserAnnotation,
  targetTrack: AnnotationTrack,
): AnnotationRange | null {
  const pairs = (detail.translation_alignment ?? []).flatMap(
    (chunk) => chunk.span_pairs ?? [],
  );
  const overlappingPairs = pairs.filter((pair) =>
    rangesOverlap(annotationRange(annotation), pairRange(pair, annotation.track)),
  );
  if (overlappingPairs.length === 0) {
    return null;
  }

  const targetRanges = overlappingPairs
    .map((pair) => pairRange(pair, targetTrack))
    .filter((range) => range.end > range.start);
  if (targetRanges.length === 0) {
    return null;
  }

  return {
    start: Math.min(...targetRanges.map((range) => range.start)),
    end: Math.max(...targetRanges.map((range) => range.end)),
  };
}

function pairRange(
  pair: TranslationSpanPair,
  track: AnnotationTrack,
): AnnotationRange {
  return track === "original"
    ? {
        start: pair.original_start_offset,
        end: pair.original_end_offset,
      }
    : {
        start: pair.english_start_offset,
        end: pair.english_end_offset,
      };
}

function annotationRange(annotation: UserAnnotation): AnnotationRange {
  return {
    start: annotation.start_offset,
    end: annotation.end_offset,
  };
}

function rangesOverlap(left: AnnotationRange, right: AnnotationRange): boolean {
  return left.start < right.end && left.end > right.start;
}

function hasExactAnnotation(
  annotations: UserAnnotation[],
  target: MirroredAnnotationTarget,
): boolean {
  return annotations.some(
    (annotation) =>
      annotation.track === target.track &&
      annotation.paragraph_id === target.paragraphId &&
      annotation.start_offset === target.range.start &&
      annotation.end_offset === target.range.end,
  );
}

function normalizedRange(
  start: number,
  end: number,
  maxEnd: number,
): AnnotationRange | null {
  const normalizedStart = Math.max(0, Math.min(start, maxEnd));
  const normalizedEnd = Math.max(normalizedStart, Math.min(end, maxEnd));
  if (normalizedEnd <= normalizedStart) {
    return null;
  }
  return {
    start: normalizedStart,
    end: normalizedEnd,
  };
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(value, 1));
}
