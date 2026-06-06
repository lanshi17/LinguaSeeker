interface SegmentCardProps {
  sourceText: string;
  targetText: string;
  sourceLang?: string;
  targetLang?: string;
}

export function SegmentCard({
  sourceText,
  targetText,
  sourceLang,
  targetLang,
}: SegmentCardProps) {
  return (
    <div className="grid gap-4 border-b border-gray-100 py-3 md:grid-cols-2">
      <div>
        {sourceLang && (
          <span className="mb-1 block text-xs font-medium text-gray-400">
            {sourceLang}
          </span>
        )}
        <p className="text-sm text-gray-800">{sourceText}</p>
      </div>
      <div>
        {targetLang && (
          <span className="mb-1 block text-xs font-medium text-gray-400">
            {targetLang}
          </span>
        )}
        <p className="text-sm text-gray-800">{targetText}</p>
      </div>
    </div>
  );
}
