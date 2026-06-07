/**
 * Custom chat provider for the ACMG Lingua backend.
 *
 * Backend chat agent flow:
 * 1. POST /api/v1/chat/sessions/{id}/messages  → persist user message
 * 2. GET  /api/v1/chat/sessions/{id}/stream?user_message=...  → SSE stream
 *
 * SSE format (standard `data:` lines, no `event:` lines):
 *   data: {"type": "text", "content": "some token"}
 *   data: {"type": "done"}
 *   data: {"type": "error", "message": "something went wrong"}
 *
 * The backend's intent detection auto-classifies messages:
 *   - "question" → LLM generates a reply (streamed)
 *   - "correction" → hardcoded confirmation
 *   - "note" → no reply generated
 *
 * The agent has access to evidence context when evidence_id is provided.
 */

import { AbstractChatProvider, XRequest } from "@ant-design/x-sdk";
import type { SSEOutput } from "@ant-design/x-sdk";
import type {
  TransformMessage,
} from "@ant-design/x-sdk/es/chat-providers/AbstractChatProvider";
import { apiClient } from "@/lib/api/client";

/** Message shape used by @ant-design/x Bubble components. */
interface ChatMessage {
  role: string;
  content: string;
}

/**
 * Custom provider that binds to the ACMG Lingua backend's chat agent.
 *
 * On request:
 * 1. Persists the user message via POST /chat/sessions/{id}/messages
 * 2. Opens SSE stream via GET /chat/sessions/{id}/stream?user_message=...
 * 3. The backend agent (ReasoningLLMProvider) generates a streamed reply
 * 4. Tokens are parsed from the SSE stream and displayed in real-time
 */
class AcmgChatProvider extends AbstractChatProvider<ChatMessage, unknown, SSEOutput> {
  private sessionId: string;

  constructor(sessionId: string) {
    // Create an XRequest that points to the stream endpoint.
    // The actual POST happens in transformParams before XRequest runs.
    const baseURL = `/api/v1/chat/sessions/${sessionId}/stream`;

    const request = XRequest<unknown, SSEOutput>(baseURL, {
      manual: true,
      // Use default SSE parser — backend sends standard `data:` lines.
      // The parser extracts {data: "..."} from each SSE line.
      // JSON parsing of the data content happens in useXChat's parser.
    });

    super({ request });
    this.sessionId = sessionId;
  }

  /**
   * Called before XRequest.run(). We don't send a body to the stream
   * endpoint — the user message was already persisted via POST.
   * Return empty params since the stream endpoint uses query params
   * set by the XRequest configuration.
   */
  transformParams(): unknown {
    return {};
  }

  /**
   * Create the local user message for display in the chat bubble.
   */
  transformLocalMessage(): ChatMessage {
    // The user message content is managed by useXChat internally.
    // This is called to create a display message — we return a placeholder
    // since the actual content comes from the useXChat request params.
    return { role: "user", content: "" };
  }

  /**
   * Not used in our flow — the stream handles token accumulation.
   */
  transformMessage(info: TransformMessage<ChatMessage, SSEOutput>): ChatMessage {
    return info.originMessage ?? { role: "assistant", content: "" };
  }
}

/**
 * Create a chat provider for a specific session.
 *
 * This creates an AcmgChatProvider that:
 * - Persists messages to the backend
 * - Streams AI replies from the backend's ReasoningLLMProvider
 * - Supports evidence context injection via evidence_id
 */
export function createAcmgChatProvider(sessionId: string) {
  return new AcmgChatProvider(sessionId);
}

/**
 * Send a user message to the backend (persist + trigger AI reply).
 * Called by ChatView before opening the SSE stream.
 */
export async function sendChatMessage(
  sessionId: string,
  content: string,
  evidenceId?: string,
): Promise<void> {
  await apiClient.post(`/chat/sessions/${sessionId}/messages`, {
    content,
    role: "user",
    ...(evidenceId ? { evidence_id: evidenceId } : {}),
  });
}
