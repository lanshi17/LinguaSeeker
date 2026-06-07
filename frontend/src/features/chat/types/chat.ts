/** Message role in a chat conversation. */
export type ChatRole = "user" | "assistant" | "system";

/** GET /chat/sessions response item. */
export interface ChatSessionResponse {
  session_id: string;
  processing_run_id: string;
  created_at: string;
  message_count: number;
}

/** Raw backend chat session response. */
export interface BackendChatSessionResponse {
  chat_session_id: string;
  processing_run_id: string;
  created_at: string;
  message_count: number;
}

/** GET /chat/sessions/{id}/messages response item. */
export interface ChatMessageResponse {
  message_id: string;
  role: ChatRole;
  content: string;
  evidence_id?: string;
  entity_id?: string;
  created_at: string;
}

/** SSE event from GET /chat/sessions/{id}/stream. */
export interface ChatSSEEvent {
  event: "token" | "done" | "error";
  data: string;
}
