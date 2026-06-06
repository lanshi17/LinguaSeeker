/**
 * Custom chat provider for the ACMG Lingua backend.
 *
 * The backend's chat API is NOT OpenAI-compatible:
 * - POST /api/v1/chat/sessions/{id}/messages  → send a message
 * - GET  /api/v1/chat/sessions/{id}/stream     → SSE stream with event/data pairs
 *
 * This provider uses DefaultChatProvider with a custom fetch that
 * adapts our backend's SSE format into the standard SSEOutput shape
 * { data: string; event?: string } that @ant-design/x-sdk expects.
 */

import { DefaultChatProvider, XRequest } from "@ant-design/x-sdk";
import type { SSEOutput } from "@ant-design/x-sdk";

/** Shape of messages sent to our backend. */
interface AcmgChatInput {
  messages: Array<{ role: string; content: string }>;
  session_id: string;
}

/**
 * Custom fetch that reads our backend's SSE stream and converts it
 * into a ReadableStream of SSEOutput objects.
 *
 * Our backend sends:
 *   event: token
 *   data: some text
 *   (blank line)
 *
 * @ant-design/x-sdk expects SSEOutput: { data: string; event?: string }
 */
function acmgFetch(
  baseURL: string,
  options: Parameters<typeof fetch>[1],
): Promise<Response> {
  return fetch(baseURL, options).then((response) => {
    if (!response.ok || !response.body) {
      return response;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const stream = new ReadableStream<SSEOutput>({
      async start(controller) {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";

            let currentEvent = "";

            for (const line of lines) {
              const trimmed = line.trim();

              if (trimmed.startsWith("event:")) {
                currentEvent = trimmed.slice(6).trim();
              } else if (trimmed.startsWith("data:")) {
                const data = trimmed.slice(5).trim();
                if (data) {
                  controller.enqueue({
                    data,
                    event: currentEvent || undefined,
                  });
                  currentEvent = "";
                }
              }
              // Ignore empty lines and comments
            }
          }
        } catch (err) {
          controller.error(err);
        } finally {
          controller.close();
        }
      },
    });

    // Return a new Response with the transformed stream.
    return new Response(stream, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  });
}

/**
 * Create a chat provider for a specific session.
 */
export function createAcmgChatProvider(sessionId: string) {
  const baseURL = `/api/v1/chat/sessions/${sessionId}/stream`;

  const request = XRequest<AcmgChatInput, SSEOutput>(baseURL, {
    manual: true,
    fetch: acmgFetch as typeof fetch,
  });

  return new DefaultChatProvider<
    { role: string; content: string },
    AcmgChatInput,
    SSEOutput
  >({
    request,
  });
}
