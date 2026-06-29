import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatSessionResponse } from "../../../src/features/chat/types/chat";
import { useSessionConversations } from "../../../src/features/chat/components/useSessionConversations";

vi.mock("antd", async (importOriginal) => {
  const actual = await importOriginal<typeof import("antd")>();
  return {
    ...actual,
    App: {
      ...actual.App,
      useApp: () => ({
        message: { error: vi.fn() },
        modal: { confirm: vi.fn() },
      }),
    },
  };
});

vi.mock("../../../src/features/chat/hooks/useChatSessions", () => ({
  useChatSessions: vi.fn(),
}));

vi.mock("@ant-design/x-sdk", async () => {
  const React = await import("react");
  return {
    useXConversations: ({
      defaultConversations,
      defaultActiveConversationKey,
    }: {
      defaultConversations: Array<{ key: string; label: string }>;
      defaultActiveConversationKey?: string;
    }) => {
      const [conversations, setConversations] = React.useState(
        defaultConversations,
      );
      return {
        conversations,
        activeConversationKey: defaultActiveConversationKey ?? "",
        setActiveConversationKey: () => true,
        addConversation: (item: { key: string; label: string }) =>
          setConversations((prev) => [...prev, item]),
        setConversations,
        removeConversation: (key: string) =>
          setConversations((prev) => prev.filter((item) => item.key !== key)),
      };
    },
  };
});

import { useChatSessions } from "../../../src/features/chat/hooks/useChatSessions";

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

function session(id: string): ChatSessionResponse {
  return {
    session_id: id,
    processing_run_id: null,
    created_at: "2026-06-29T00:00:00Z",
    message_count: 0,
  };
}

function Wrapper({ children }: { children: ReactNode }) {
  return children;
}

describe("useSessionConversations", () => {
  it("creates a new standalone session and switches the active conversation to it", async () => {
    const createdSession = session("new-session");
    vi.mocked(useChatSessions).mockReturnValue({
      sessions: [session("old-session")],
      isLoading: false,
      createSession: vi.fn().mockResolvedValue(createdSession),
      isCreating: false,
      removeSession: vi.fn(),
    });

    const { result } = renderHook(
      () => useSessionConversations(undefined),
      { wrapper: Wrapper },
    );

    let createdId: string | undefined;
    await act(async () => {
      createdId = await result.current.handleCreateSession();
    });

    expect(createdId).toBe("new-session");
    expect(result.current.activeConversationKey).toBe("new-session");
    expect(result.current.conversations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "new-session" }),
      ]),
    );
  });
});
