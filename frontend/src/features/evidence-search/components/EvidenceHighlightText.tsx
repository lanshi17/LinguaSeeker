"use client";

import type {
  EvidenceChainHighlight,
  EvidenceHighlightTone,
} from "../types/evidenceSearch";

export type { EvidenceHighlightTone } from "../types/evidenceSearch";

interface EvidenceHighlightTextProps {
  highlight?: EvidenceChainHighlight | null;
  active?: boolean;
  label?: string;
  tone?: EvidenceHighlightTone;
}

const TONE_STYLES: Record<EvidenceHighlightTone, string> = {
  classification: "bg-amber-200 text-amber-950 ring-1 ring-amber-300",
  disease: "bg-rose-200 text-rose-950 ring-1 ring-rose-300",
  functional: "bg-success-200 text-success-950 ring-1 ring-success-300",
  gene: "bg-primary-200 text-primary-950 ring-1 ring-primary-300",
  neutral: "bg-gray-200 text-gray-950 ring-1 ring-gray-300",
  variant: "bg-cyan-200 text-cyan-950 ring-1 ring-cyan-300",
};

export function EvidenceHighlightText({
  highlight,
  active = false,
  label,
  tone = "neutral",
}: EvidenceHighlightTextProps) {
  if (!highlight || !highlight.text) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-500">
        No source span available.
      </div>
    );
  }

  const start = Math.max(0, Math.min(highlight.highlight_start, highlight.text.length));
  const end = Math.max(start, Math.min(highlight.highlight_end, highlight.text.length));
  const before = highlight.text.slice(0, start);
  const marked = highlight.text.slice(start, end);
  const after = highlight.text.slice(end);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm leading-7 text-gray-800 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-gray-500">
        {label && (
          <span className="rounded-md bg-gray-100 px-2 py-1 font-medium text-gray-700">
            {label}
          </span>
        )}
        <span>Page {highlight.page ?? "\u2014"}</span>
      </div>
      <p className="whitespace-pre-wrap">
        {before}
        <mark
          className={`rounded px-1 py-0.5 font-medium ${active ? TONE_STYLES[tone] : "bg-yellow-100 text-gray-900"}`}
        >
          {marked}
        </mark>
        {after}
      </p>
    </div>
  );
}
