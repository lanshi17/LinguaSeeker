import { cn } from "@/lib/utils/cn";
import type { LiteratureCandidateItem } from "../types/literature";

interface CandidateCardProps {
  candidate: LiteratureCandidateItem;
  selected: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

export function CandidateCard({
  candidate,
  selected,
  onToggle,
  disabled,
}: CandidateCardProps) {
  return (
    <div
      onClick={disabled ? undefined : onToggle}
      className={cn(
        "cursor-pointer rounded-lg border p-4 transition-colors",
        selected
          ? "border-primary-300 bg-primary-50"
          : "border-gray-200 bg-white hover:border-gray-300",
        disabled && !selected && "cursor-not-allowed opacity-50",
      )}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          onClick={(e) => e.stopPropagation()}
          disabled={disabled}
          className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600"
        />
        <div className="flex-1">
          <h4 className="text-sm font-medium text-gray-900">
            {candidate.title}
          </h4>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
            {candidate.journal && <span>{candidate.journal}</span>}
            {candidate.year && <span>{candidate.year}</span>}
            {candidate.doi && <span>DOI: {candidate.doi}</span>}
            <span className="rounded bg-gray-100 px-1.5 py-0.5">
              {candidate.provider}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
