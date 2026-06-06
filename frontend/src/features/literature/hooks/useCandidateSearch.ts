"use client";

import { useMutation } from "@tanstack/react-query";
import { searchCandidates } from "../services/literature";
import type {
  LiteratureCandidateSearchRequest,
  LiteratureCandidateSearchResponse,
} from "../types/literature";

export function useCandidateSearch() {
  return useMutation<
    LiteratureCandidateSearchResponse,
    Error,
    LiteratureCandidateSearchRequest
  >({
    mutationFn: searchCandidates,
  });
}
