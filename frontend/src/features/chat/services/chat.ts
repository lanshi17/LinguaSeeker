import { apiClient } from "@/lib/api/client";
import type { ChatSessionResponse, ChatMessageResponse } from "../types/chat";

export async function createSession(
  processingRunId: string,
): Promise<ChatSessionResponse> {
  const { data } = await apiClient.post<ChatSessionResponse>(
    "/chat/sessions",
    { processing_run_id: processingRunId },
  );
  return data;
}

export async function listSessions(
  processingRunId: string,
): Promise<ChatSessionResponse[]> {
  const { data } = await apiClient.get<ChatSessionResponse[]>(
    `/chat/sessions/${processingRunId}`,
  );
  return data;
}

export async function listMessages(
  sessionId: string,
  limit = 100,
): Promise<ChatMessageResponse[]> {
  const { data } = await apiClient.get<ChatMessageResponse[]>(
    `/chat/sessions/${sessionId}/messages`,
    { params: { limit } },
  );
  return data;
}

export async function appendMessage(
  sessionId: string,
  content: string,
  evidenceId?: string,
): Promise<ChatMessageResponse> {
  const { data } = await apiClient.post<ChatMessageResponse>(
    `/chat/sessions/${sessionId}/messages`,
    { content, evidence_id: evidenceId },
  );
  return data;
}

/** Build the SSE stream URL for a chat session. */
export function streamUrl(sessionId: string): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";
  return `${base}/chat/sessions/${sessionId}/stream`;
}
