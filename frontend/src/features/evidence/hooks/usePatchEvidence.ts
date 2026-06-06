"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { patchEvidence } from "../services/evidence";
import type { EvidencePatchRequest, PatchResultResponse } from "../types/evidence";

export function usePatchEvidence(evidenceId: string) {
  const queryClient = useQueryClient();

  return useMutation<PatchResultResponse, Error, EvidencePatchRequest>({
    mutationFn: (body) => patchEvidence(evidenceId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evidence", evidenceId] });
    },
  });
}
