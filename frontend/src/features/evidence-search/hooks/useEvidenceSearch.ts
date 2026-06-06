"use client";

import { useMutation } from "@tanstack/react-query";
import { searchEvidence } from "../services/evidenceSearch";
import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
} from "../types/evidenceSearch";

/** Mutation hook for evidence search. */
export function useEvidenceSearch() {
  return useMutation<EvidenceSearchResponse, Error, EvidenceSearchQuery>({
    mutationFn: searchEvidence,
  });
}
