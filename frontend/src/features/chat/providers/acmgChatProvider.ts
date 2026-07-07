/**
 * Custom chat provider for the Lingua Seeker backend.
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
import { ApiError } from "@/lib/api/error";
import type { ChatBubbleMessage } from "../utils/messageHistory";
import { removeLocalChatSession } from "../utils/localSessions";
import { buildAppendMessageBody } from "../utils/messageRequests";
import { appendAssistantChunk } from "../utils/sse";

interface ChatRequestParams {
  messages?: ChatBubbleMessage[];
}

function appendHeaderValue(
  headers: Headers,
  key: string,
  value: unknown,
): void {
  if (
    value === undefined ||
    value === null ||
    typeof value === "object" ||
    typeof value === "function"
  ) {
    return;
  }
  headers.set(key, String(value));
}

function appendHeaderSource(headers: Headers, source: unknown): void {
  if (!source || typeof source !== "object") return;

  if (source instanceof Headers) {
    source.forEach((value, key) => headers.set(key, value));
    return;
  }

  if ("toJSON" in source && typeof source.toJSON === "function") {
    appendHeaderSource(headers, source.toJSON());
    return;
  }

  for (const [key, value] of Object.entries(source)) {
    if (["common", "delete", "get", "head", "post", "put", "patch"].includes(key)) {
      continue;
    }
    appendHeaderValue(headers, key, value);
  }
}

function buildStreamHeaders(sdkHeaders?: HeadersInit): Headers {
  const headers = new Headers(sdkHeaders);
  const defaultHeaders = apiClient.defaults.headers;
  if (defaultHeaders && typeof defaultHeaders === "object") {
    appendHeaderSource(headers, "common" in defaultHeaders ? defaultHeaders.common : null);
    appendHeaderSource(headers, defaultHeaders);
  }
  return headers;
}

/**
 * Custom provider that binds to the Lingua Seeker backend's chat agent.
 *
 * On request:
 * 1. Persists the user message via POST /chat/sessions/{id}/messages
 * 2. Opens SSE stream via GET /chat/sessions/{id}/stream?user_message=...
 * 3. The backend agent (ReasoningLLMProvider) generates a streamed reply
 * 4. Tokens are parsed from the SSE stream and displayed in real-time
 */
class AcmgChatProvider extends AbstractChatProvider<
  ChatBubbleMessage,
  unknown,
  SSEOutput
> {
  private sessionId: string;
  /** Abort the in-flight SSE stream, if any. Safe to call at any time. */
  abort: () => void;
  /** Whether a stream request is currently in flight. */
  get isStreaming(): boolean {
    // Implemented via instance getter defined in constructor.
    // (TypeScript needs this declaration to know the property exists.)
    return false;
  }

  constructor(sessionId: string) {
    // Closure variables for abort state.  We use closures rather than
    // instance fields so that the fetch function (defined before super())
    // can reference them without needing `this` — derived classes cannot
    // access `this` before super() is called, but closure variables are
    // valid from declaration onward.
    let abortController: AbortController | null = null;
    let streaming = false;
    let streamAborted = false;

    // Create an XRequest that points to the stream endpoint.
    // The actual POST happens in ChatView before XRequest runs.
    const baseURL = `${apiClient.defaults.baseURL}/chat/sessions/${sessionId}/stream`;

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

        // Create a fresh AbortController for each request so that
        // abort() can reliably cancel the in-flight fetch.
        abortController = new AbortController();
        streaming = true;
        streamAborted = false;

        // Combine our controller's signal with the SDK's signal so that
        // both our abort() and the SDK's internal abort work.
        const signals: AbortSignal[] = [abortController.signal];
        if (options.signal) {
          signals.push(options.signal);
          options.signal.addEventListener(
            "abort",
            () => {
              streamAborted = true;
            },
            { once: true },
          );
        }
        const combinedSignal =
          signals.length > 1
            ? AbortSignal.any(signals)
            : signals[0];

        const doFetch = fetch(streamUrl, {
          method: "GET",
          headers: buildStreamHeaders(options.headers),
          credentials: "include",
          signal: combinedSignal,
        });

        // Reset streaming state when the request settles.
        doFetch.finally(() => {
          streaming = false;
          abortController = null;
        });

        return doFetch;
      },
    });

    super({ request });
    this.sessionId = sessionId;

    // Define instance-level abort method and isStreaming getter,
    // both backed by the closure variables above.
    this.abort = () => {
      streamAborted = true;
      if (abortController) {
        abortController.abort();
        abortController = null;
      }
      streaming = false;
    };

    Object.defineProperty(this, "isStreaming", {
      get: () => streaming,
      enumerable: true,
      configurable: true,
    });

    Object.defineProperty(this, "_isStreamAborted", {
      get: () => streamAborted,
      enumerable: true,
      configurable: true,
    });
  }

  /** Exposed via Object.defineProperty in constructor (closure-backed). */
  get _isStreamAborted(): boolean {
    return false;
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
    if (this._isStreamAborted) {
      return info.originMessage ?? { role: "assistant", content: "" };
    }
    return appendAssistantChunk(info.originMessage, info.chunk);
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
 * Send a user message to the backend (persist only).
 * Called by ChatView before opening the SSE stream.
 */
export async function sendChatMessage(
  sessionId: string,
  content: string,
  evidenceId?: string,
): Promise<void> {
  try {
    await apiClient.post(
      `/chat/sessions/${sessionId}/messages`,
      buildAppendMessageBody(content, evidenceId),
    );
  } catch (err) {
    // Stale session in localStorage (e.g. DB was reset). Remove it so
    // it doesn't reappear on next page load, then surface the error.
    if (err instanceof ApiError && err.status === 404) {
      removeLocalChatSession(undefined, sessionId);
    }
    throw err;
  }
}
