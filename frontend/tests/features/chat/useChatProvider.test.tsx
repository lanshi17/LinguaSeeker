import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useChatProvider } from "../../../src/features/chat/components/useChatProvider";
import { listMessages } from "../../../src/features/chat/services/chat";

vi.mock("../../../src/features/chat/providers/acmgChatProvider", () => ({
  createAcmgChatProvider: vi.fn((sessionId: string) => ({
    abort: vi.fn(),
    sessionId,
  })),
}));

vi.mock("../../../src/features/chat/services/chat", () => ({
  listMessages: vi.fn(),
}));

vi.mock("@ant-design/x-sdk", () => ({
  useXChat: vi.fn(() => ({
    messages: [],
    onRequest: vi.fn(),
    isRequesting: false,
    abort: vi.fn(),
    setMessages: vi.fn(),
  })),
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe("useChatProvider", () => {
  it("does not reload history just because setMessages identity changes", async () => {
    vi.mocked(listMessages).mockResolvedValue([]);

    const { rerender } = renderHook(
      ({ sessionId }: { sessionId: string }) => useChatProvider(sessionId),
      { initialProps: { sessionId: "session-a" } },
    );

    await waitFor(() => {
      expect(listMessages).toHaveBeenCalledTimes(1);
    });

    rerender({ sessionId: "session-a" });

    expect(listMessages).toHaveBeenCalledTimes(1);
  });

  it("loads history when the active conversation changes", async () => {
    vi.mocked(listMessages).mockResolvedValue([]);

    const { rerender } = renderHook(
      ({ sessionId }: { sessionId: string }) => useChatProvider(sessionId),
      { initialProps: { sessionId: "session-a" } },
    );

    await waitFor(() => {
      expect(listMessages).toHaveBeenCalledWith("session-a");
    });

    rerender({ sessionId: "session-b" });

    await waitFor(() => {
      expect(listMessages).toHaveBeenCalledWith("session-b");
    });
  });
});
