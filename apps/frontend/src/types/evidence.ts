export type EvidenceHighlight = {
  kind: 'evidence' | 'acmg' | 'user';
  sourceRanges?: Array<{ start: number; end: number }>;
  targetRanges?: Array<{ start: number; end: number }>;
  label?: string;
};

export type EvidenceSegment = {
  id: string;
  sourceText: string;
  targetText: string;
  groupId?: string;
  highlights?: EvidenceHighlight[];
};

export type EvidenceViewModel = {
  sourceLang: string;
  targetLang: string;
  segments: EvidenceSegment[];
  raw?: unknown;
  warning?: string;
};
