import { apiClient } from "@/lib/api/client";
import type {
  BackendChatSessionResponse,
  ChatSessionResponse,
  ChatMessageResponse,
} from "../types/chat";

function normalizeSession(session: BackendChatSessionResponse): ChatSessionResponse {
  return {
    session_id: session.chat_session_id,
    processing_run_id: session.processing_run_id,
    created_at: session.created_at,
    message_count: session.message_count,
  };
}

export async function createSession(
  processingRunId: string,
): Promise<ChatSessionResponse> {
  const { data } = await apiClient.post<BackendChatSessionResponse>(
    "/chat/sessions",
    { processing_run_id: processingRunId },
  );
  return normalizeSession(data);
}

export async function listSessions(
  processingRunId: string,
): Promise<ChatSessionResponse[]> {
  const { data } = await apiClient.get<BackendChatSessionResponse[]>(
    `/chat/sessions/${processingRunId}`,
  );
  return data.map(normalizeSession);
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
