"use client";

import { CandidateCard } from "./CandidateCard";
import { Spinner } from "@/components/ui/Spinner";
import type { LiteratureCandidateItem } from "../types/literature";

interface LiteratureCandidateListProps {
  candidates: LiteratureCandidateItem[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
  isLoading?: boolean;
  isAtLimit?: boolean;
}

export function LiteratureCandidateList({
  candidates,
  selectedIds,
  onToggle,
  isLoading,
  isAtLimit,
}: LiteratureCandidateListProps) {
  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  if (candidates.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-gray-500">
        No candidates found.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {candidates.map((c) => (
        <CandidateCard
          key={c.candidate_id}
          candidate={c}
          selected={selectedIds.has(c.candidate_id)}
          onToggle={() => onToggle(c.candidate_id)}
          disabled={isAtLimit && !selectedIds.has(c.candidate_id)}
        />
      ))}
    </div>
  );
}
