"use client";

import type { EvidenceChainHighlight } from "../types/evidenceSearch";

interface EvidenceHighlightTextProps {
  highlight?: EvidenceChainHighlight | null;
  active?: boolean;
}

export function EvidenceHighlightText({
  highlight,
  active = false,
}: EvidenceHighlightTextProps) {
  if (!highlight || !highlight.text) {
    return <p className="text-sm text-gray-400">No source span available.</p>;
  }

  const start = Math.max(0, Math.min(highlight.highlight_start, highlight.text.length));
  const end = Math.max(start, Math.min(highlight.highlight_end, highlight.text.length));
  const before = highlight.text.slice(0, start);
  const marked = highlight.text.slice(start, end);
  const after = highlight.text.slice(end);

  return (
    <div className="rounded-md border border-gray-200 bg-white p-3 text-sm leading-6 text-gray-700">
      <div className="mb-2 text-xs text-gray-400">
        Page {highlight.page ?? "—"}
      </div>
      <p className="whitespace-pre-wrap">
        {before}
        <mark
          className={
            active
              ? "rounded bg-amber-200 px-0.5 text-gray-950"
              : "rounded bg-yellow-100 px-0.5 text-gray-900"
          }
        >
          {marked}
        </mark>
        {after}
      </p>
    </div>
  );
}
