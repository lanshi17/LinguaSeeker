/** Message role in a chat conversation. */
export type ChatRole = "user" | "assistant" | "system";

/** Normalized chat session used by the frontend. */
export interface ChatSessionResponse {
  session_id: string;
  processing_run_id: string | null;
  created_at: string;
  message_count: number;
}

/** Raw backend chat session response. */
export interface BackendChatSessionResponse {
  chat_session_id: string;
  processing_run_id: string | null;
  created_at: string;
  message_count: number;
}

/** GET /chat/sessions/{id}/messages response item. */
export interface ChatMessageResponse {
  message_id: string;
  chat_session_id: string;
  role: ChatRole;
  content: string;
  evidence_id?: string | null;
  entity_id?: string | null;
  created_at: string;
}
