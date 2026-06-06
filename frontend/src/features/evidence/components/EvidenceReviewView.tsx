"use client";

import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { EvidenceCard } from "./EvidenceCard";
import { EvidencePatchForm } from "./EvidencePatchForm";
import { BilingualSpanView } from "@/features/source-link";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";

interface EvidenceReviewViewProps {
  evidenceId: string;
}

/** Client wrapper for evidence review. Wired by the page shell. */
export function EvidenceReviewView({ evidenceId }: EvidenceReviewViewProps) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["evidence", evidenceId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/evidence/${evidenceId}`);
      return data as Record<string, unknown>;
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="py-10 text-center">
        <p className="text-sm text-red-600">Failed to load evidence.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <ErrorBoundary>
        <EvidenceCard
          status={(data?.status as string as "provisional") ?? "provisional"}
          data={data}
        />
      </ErrorBoundary>

      <ErrorBoundary>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-gray-700">
            Update Status
          </h3>
          <EvidencePatchForm
            evidenceId={evidenceId}
            currentStatus={
              (data?.status as string as "provisional") ?? "provisional"
            }
            onPatched={() => refetch()}
          />
        </Card>
      </ErrorBoundary>

      <ErrorBoundary>
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-gray-700">
            Source Traceability
          </h3>
          <BilingualSpanView evidenceId={evidenceId} />
        </Card>
      </ErrorBoundary>
    </div>
  );
}
