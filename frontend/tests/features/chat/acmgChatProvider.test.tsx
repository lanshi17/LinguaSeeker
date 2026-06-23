import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createAcmgChatProvider,
  sendChatMessage,
} from "../../../src/features/chat/providers/acmgChatProvider";
import { apiClient } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    defaults: { baseURL: "/api/v1" },
    post: vi.fn(),
  },
}));

/**
 * Helper to invoke the XRequest on a provider instance.
 * XRequest instances from @ant-design/x-sdk have a `run` method that
 * starts the fetch synchronously (it may return a non-Promise value).
 */
function triggerRequest(
  provider: ReturnType<typeof createAcmgChatProvider>,
  params: unknown,
): void {
  const request = (provider as unknown as { request: { run?: unknown } }).request;
  if (request && typeof (request as { run: unknown }).run === "function") {
    void (request as { run: (p: unknown) => unknown }).run(params);
    return;
  }
  throw new Error(
    `Cannot invoke XRequest. Type: ${typeof request}, keys: ${Object.keys(request ?? {})}`,
  );
}

describe("AcmgChatProvider — abort behaviour", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("exposes an abort() method", () => {
    const provider = createAcmgChatProvider("session-123");
    expect(typeof provider.abort).toBe("function");
  });

  it("exposes an isStreaming getter (false by default)", () => {
    const provider = createAcmgChatProvider("session-456");
    expect(provider.isStreaming).toBe(false);
  });

  it("abort() is safe to call when no request is active (idempotent)", () => {
    const provider = createAcmgChatProvider("session-789");
    expect(() => provider.abort()).not.toThrow();
    expect(() => provider.abort()).not.toThrow();
    expect(provider.isStreaming).toBe(false);
  });

  it("abort() cancels an in-flight fetch via AbortController", async () => {
    // Mock fetch with a Promise that never resolves, simulating
    // a long-running SSE stream.  We capture the signal to verify abort.
    let capturedSignal: AbortSignal | null | undefined;

    const pendingResponse = new Promise<Response>(() => {
      // Never resolves — we abort it instead.
    });

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, options) => {
        capturedSignal = options?.signal;
        return pendingResponse;
      },
    );

    const provider = createAcmgChatProvider("session-abort-test");

    // Start the request synchronously
    triggerRequest(provider, {
      messages: [{ role: "user", content: "Hello" }],
    });

    // Give the microtask queue a tick so fetch() is invoked
    await Promise.resolve();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(capturedSignal).toBeDefined();
    expect(capturedSignal?.aborted).toBe(false);
    expect(provider.isStreaming).toBe(true);

    // Abort the stream via the provider's abort method
    provider.abort();

    expect(capturedSignal?.aborted).toBe(true);
    expect(provider.isStreaming).toBe(false);
  });

  it("isStreaming becomes false after a request completes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("data: {\"type\": \"done\"}\n\n", {
        headers: { "Content-Type": "text/event-stream" },
      }),
    );

    const provider = createAcmgChatProvider("session-streaming-test");

    expect(provider.isStreaming).toBe(false);

    triggerRequest(provider, {
      messages: [{ role: "user", content: "Hello" }],
    });

    // The fetch was initiated; wait for it to settle
    await new Promise((r) => setTimeout(r, 10));

    expect(provider.isStreaming).toBe(false);
  });

  it("constructs the stream URL with sessionId and user_message query param", async () => {
    let fetchedUrl = "";

    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      fetchedUrl = typeof url === "string" ? url : url.toString();
      return Promise.resolve(
        new Response("data: {\"type\": \"done\"}\n\n", {
          headers: { "Content-Type": "text/event-stream" },
        }),
      );
    });

    const provider = createAcmgChatProvider("session-url-test");

    triggerRequest(provider, {
      messages: [{ role: "user", content: "Hello there" }],
    });

    // Wait for fetch microtask
    await Promise.resolve();

    expect(fetchedUrl).toContain("/api/v1/chat/sessions/session-url-test/stream");
    // URLSearchParams encodes spaces as '+' (application/x-www-form-urlencoded)
    expect(fetchedUrl).toContain("user_message=Hello+there");
  });

  it("combines SDK signal with own AbortController signal (both can abort)", async () => {
    let capturedSignal: AbortSignal | null | undefined;

    const pendingResponse = new Promise<Response>(() => {});

    vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      capturedSignal = options?.signal;
      return pendingResponse;
    });

    const provider = createAcmgChatProvider("session-signal-test");

    triggerRequest(provider, {
      messages: [{ role: "user", content: "Hi" }],
    });

    await Promise.resolve();

    // Signal should not be aborted initially
    expect(capturedSignal?.aborted).toBe(false);
    expect(provider.isStreaming).toBe(true);

    // Abort via provider — should abort the combined signal
    provider.abort();
    expect(capturedSignal?.aborted).toBe(true);
    expect(provider.isStreaming).toBe(false);
  });
});

describe("sendChatMessage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("POSTs a message to the correct endpoint", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} });

    await sendChatMessage("sess-1", "Hello world");

    expect(apiClient.post).toHaveBeenCalledWith(
      "/chat/sessions/sess-1/messages",
      expect.objectContaining({
        role: "user",
        content: "Hello world",
      }),
    );
  });

  it("includes evidence_id when provided", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} });

    await sendChatMessage("sess-1", "test", "ev-123");

    expect(apiClient.post).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        evidence_id: "ev-123",
      }),
    );
  });
});
