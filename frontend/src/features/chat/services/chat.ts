import { apiClient } from "@/lib/api/client";
import { ApiError } from "@/lib/api/error";
import type {
  BackendChatSessionResponse,
  ChatMessageResponse,
  ChatSessionResponse,
} from "../types/chat";
import { removeLocalChatSession } from "../utils/localSessions";
import { buildAppendMessageBody } from "../utils/messageRequests";

function normalizeSession(session: BackendChatSessionResponse): ChatSessionResponse {
  return {
    session_id: session.chat_session_id,
    processing_run_id: session.processing_run_id,
    title: session.title ?? null,
    created_at: session.created_at,
    message_count: session.message_count,
  };
}

export async function createSession(
  processingRunId?: string | null,
): Promise<ChatSessionResponse> {
  const body = processingRunId ? { processing_run_id: processingRunId } : {};
  const { data } = await apiClient.post<BackendChatSessionResponse>(
    "/chat/sessions",
    body,
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

export async function getSession(sessionId: string): Promise<ChatSessionResponse> {
  const { data } = await apiClient.get<BackendChatSessionResponse>(
    `/chat/session-details/${sessionId}`,
  );
  return normalizeSession(data);
}

export async function listMessages(
  sessionId: string,
  limit = 100,
): Promise<ChatMessageResponse[]> {
  try {
    const { data } = await apiClient.get<ChatMessageResponse[]>(
      `/chat/sessions/${sessionId}/messages`,
      { params: { limit } },
    );
    return data;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      removeLocalChatSession(undefined, sessionId);
    }
    throw err;
  }
}

export async function appendMessage(
  sessionId: string,
  content: string,
  evidenceId?: string,
): Promise<ChatMessageResponse> {
  const { data } = await apiClient.post<ChatMessageResponse>(
    `/chat/sessions/${sessionId}/messages`,
    buildAppendMessageBody(content, evidenceId),
  );
  return data;
}

/** Build the SSE stream URL for a chat session. */
export function streamUrl(sessionId: string): string {
  return `${apiClient.defaults.baseURL}/chat/sessions/${sessionId}/stream`;
}
