import { SegmentCard } from "./SegmentCard";

interface Segment {
  source: string;
  target: string;
}

interface BilingualReadingPaneProps {
  segments: Segment[];
  sourceLang?: string;
  targetLang?: string;
}

export function BilingualReadingPane({
  segments,
  sourceLang,
  targetLang,
}: BilingualReadingPaneProps) {
  if (segments.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-gray-500">
        No text segments available.
      </p>
    );
  }

  return (
    <div>
      {segments.map((seg, i) => (
        <SegmentCard
          key={i}
          sourceText={seg.source}
          targetText={seg.target}
          sourceLang={sourceLang}
          targetLang={targetLang}
        />
      ))}
    </div>
  );
}
