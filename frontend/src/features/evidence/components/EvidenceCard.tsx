import { Card } from "@/components/ui/Card";
import { EvidenceStatusBadge } from "./EvidenceStatusBadge";
import type { ReviewStatus } from "../types/evidence";

interface EvidenceCardProps {
  evidenceId: string;
  status: ReviewStatus;
  data?: Record<string, unknown>;
  onEdit?: () => void;
}

export function EvidenceCard({
  status,
  data,
  onEdit,
}: EvidenceCardProps) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <EvidenceStatusBadge status={status} />
        {onEdit && (
          <button
            onClick={onEdit}
            className="cursor-pointer text-sm text-primary-600 hover:underline"
          >
            Edit
          </button>
        )}
      </div>
      {data && (
        <pre className="mt-3 max-h-64 overflow-auto rounded bg-gray-50 p-3 text-xs text-gray-700">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </Card>
  );
}
