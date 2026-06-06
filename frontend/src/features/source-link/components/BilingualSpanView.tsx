"use client";

import { TrackSpanView } from "./TrackSpanView";
import { Spinner } from "@/components/ui/Spinner";
import { useBilingualSpan } from "../hooks/useBilingualSpan";

interface BilingualSpanViewProps {
  evidenceId: string;
}

export function BilingualSpanView({ evidenceId }: BilingualSpanViewProps) {
  const { data, isLoading, error } = useBilingualSpan(evidenceId);

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <p className="py-10 text-center text-sm text-gray-500">
        No bilingual source data available.
      </p>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <TrackSpanView span={data.original} />
      <TrackSpanView span={data.translated} />
    </div>
  );
}
