import { Badge } from "@/components/ui/Badge";
import type { ReviewStatus } from "../types/evidence";

interface EvidenceStatusBadgeProps {
  status: ReviewStatus;
}

const variantMap: Record<ReviewStatus, "default" | "success" | "warning" | "error" | "info"> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

export function EvidenceStatusBadge({ status }: EvidenceStatusBadgeProps) {
  return <Badge variant={variantMap[status]}>{status}</Badge>;
}
