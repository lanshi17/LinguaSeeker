"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { usePatchEvidence } from "../hooks/usePatchEvidence";
import type { ReviewStatus, EvidencePatchRequest } from "../types/evidence";

interface EvidencePatchFormProps {
  evidenceId: string;
  currentStatus: ReviewStatus;
  onPatched?: () => void;
}

export function EvidencePatchForm({
  evidenceId,
  currentStatus,
  onPatched,
}: EvidencePatchFormProps) {
  const { mutateAsync, isPending } = usePatchEvidence(evidenceId);
  const [status, setStatus] = useState<ReviewStatus>(currentStatus);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const body: EvidencePatchRequest = { status };
    await mutateAsync(body);
    onPatched?.();
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-3">
      <Select
        label="Status"
        value={status}
        onChange={(e) => setStatus(e.target.value as ReviewStatus)}
        options={[
          { label: "Provisional", value: "provisional" },
          { label: "Approved", value: "approved" },
          { label: "Corrected", value: "corrected" },
          { label: "Rejected", value: "rejected" },
        ]}
      />
      <Button type="submit" size="sm" loading={isPending}>
        Update
      </Button>
    </form>
  );
}
