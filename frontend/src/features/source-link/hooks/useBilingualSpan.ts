"use client";

import { useQuery } from "@tanstack/react-query";
import { getBilingualSpan } from "../services/sourceLink";

export function useBilingualSpan(evidenceId: string) {
  return useQuery({
    queryKey: ["source-link", "bilingual", evidenceId],
    queryFn: () => getBilingualSpan(evidenceId),
  });
}
