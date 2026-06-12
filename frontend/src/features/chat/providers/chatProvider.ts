/**
 * Custom chat provider for the Cross Evidence backend.
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
import type { TransformMessage } from "@ant-design/x-sdk/es/chat-providers/AbstractChatProvider";
import { apiClient } from "@/lib/api/client";
import type { ChatBubbleMessage } from "../utils/messageHistory";
import { buildAppendMessageBody } from "../utils/messageRequests";
import { appendAssistantChunk } from "../utils/sse";

interface ChatRequestParams {
  messages?: ChatBubbleMessage[];
}

/**
 * Custom provider that binds to the Cross Evidence backend's chat agent.
 *
 * On request:
 * 1. Persists the user message via POST /chat/sessions/{id}/messages
 * 2. Opens SSE stream via GET /chat/sessions/{id}/stream?user_message=...
 * 3. The backend agent (ReasoningLLMProvider) generates a streamed reply
 * 4. Tokens are parsed from the SSE stream and displayed in real-time
 */
class CrossEvidenceChatProvider extends AbstractChatProvider<
  ChatBubbleMessage,
  unknown,
  SSEOutput
> {
  private sessionId: string;

  constructor(sessionId: string) {
    // Create an XRequest that points to the stream endpoint.
    // The actual POST happens in ChatView before XRequest runs.
    const baseURL = `/api/v1/chat/sessions/${sessionId}/stream`;

    const request = XRequest<unknown, SSEOutput>(baseURL, {
      manual: true,
      fetch: (url, options) => {
        const params = options.params as ChatRequestParams;
        const latestMessage = params.messages?.at(-1)?.content;
        if (!latestMessage) {
          throw new Error("Cannot stream chat reply without a user message.");
        }

        const streamUrl = new URL(url.toString(), window.location.origin);
        streamUrl.searchParams.set("user_message", latestMessage);

        return fetch(streamUrl, {
          method: "GET",
          headers: options.headers,
          signal: options.signal,
        });
      },
    });

    super({ request });
    this.sessionId = sessionId;
  }

  /**
   * Called before XRequest.run(). We don't send a body to the stream
   * endpoint — the user message was already persisted via POST.
   * Return request params so the custom fetch can place the latest user
   * message into the stream endpoint query string.
   */
  transformParams(requestParams: ChatRequestParams): ChatRequestParams {
    return requestParams;
  }

  /**
   * Create the local user message for display in the chat bubble.
   */
  transformLocalMessage(requestParams: ChatRequestParams): ChatBubbleMessage {
    return requestParams.messages?.at(-1) ?? { role: "user", content: "" };
  }

  /**
   * Accumulate streamed backend chunks into the visible assistant message.
   */
  transformMessage(
    info: TransformMessage<ChatBubbleMessage, SSEOutput>,
  ): ChatBubbleMessage {
    return appendAssistantChunk(info.originMessage, info.chunk);
  }
}

/**
 * Create a chat provider for a specific session.
 *
 * This creates a CrossEvidenceChatProvider that:
 * - Persists messages to the backend
 * - Streams AI replies from the backend's ReasoningLLMProvider
 * - Supports evidence context injection via evidence_id
 */
export function createCrossEvidenceChatProvider(sessionId: string) {
  return new CrossEvidenceChatProvider(sessionId);
}

/**
 * Send a user message to the backend (persist only).
 * Called by ChatView before opening the SSE stream.
 */
export async function sendChatMessage(
  sessionId: string,
  content: string,
  evidenceId?: string,
): Promise<void> {
  await apiClient.post(
    `/chat/sessions/${sessionId}/messages`,
    buildAppendMessageBody(content, evidenceId),
  );
}
