"use client";

import { useQuery } from "@tanstack/react-query";
import { getTrackSpan } from "../services/sourceLink";

export function useTrackSpan(
  evidenceId: string,
  track: "original" | "translated",
) {
  return useQuery({
    queryKey: ["source-link", "track", evidenceId, track],
    queryFn: () => getTrackSpan(evidenceId, track),
  });
}
