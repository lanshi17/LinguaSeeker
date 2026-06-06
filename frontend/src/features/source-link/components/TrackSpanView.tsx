import type { TrackSpan } from "../types/sourceLink";

interface TrackSpanViewProps {
  span: TrackSpan;
}

export function TrackSpanView({ span }: TrackSpanViewProps) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs font-medium uppercase text-gray-500">
          {span.track}
        </span>
        {span.language && (
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-400">
            {span.language}
          </span>
        )}
      </div>
      <div className="space-y-1">
        {span.spans.map((s, i) => (
          <p
            key={i}
            className="rounded bg-gray-50 p-2 text-sm text-gray-800"
            title={s.label}
          >
            {s.text}
          </p>
        ))}
      </div>
    </div>
  );
}
