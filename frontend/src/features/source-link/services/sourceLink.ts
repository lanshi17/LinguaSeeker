import { apiClient } from "@/lib/api/client";
import type { BilingualSpan, TrackSpan } from "../types/sourceLink";

export async function getBilingualSpan(
  evidenceId: string,
): Promise<BilingualSpan> {
  const { data } = await apiClient.get<BilingualSpan>(
    `/source-link/${evidenceId}/bilingual`,
  );
  return data;
}

export async function getTrackSpan(
  evidenceId: string,
  track: "original" | "translated",
): Promise<TrackSpan | null> {
  const { data } = await apiClient.get<TrackSpan | null>(
    `/source-link/${evidenceId}/${track}`,
  );
  return data;
}
