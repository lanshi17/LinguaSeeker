import "@testing-library/jest-dom/vitest";

import type React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatView } from "../../../src/features/chat/components/ChatView";

const mocks = vi.hoisted(() => ({
  createAndActivateSession: vi.fn(),
  refreshSessionTitle: vi.fn(),
  onRequest: vi.fn(),
  sendChatMessage: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/lib/i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/features/pipeline", () => ({
  TaskQueuePanel: () => <aside data-testid="task-queue" />,
}));

vi.mock("../../../src/features/chat/providers/acmgChatProvider", () => ({
  sendChatMessage: mocks.sendChatMessage,
}));

vi.mock("../../../src/features/chat/components/useChatProvider", () => ({
  useChatProvider: (activeConversationKey?: string) => ({
    activeProvider: activeConversationKey ? { abort: vi.fn() } : undefined,
    messages: [],
    onRequest: activeConversationKey ? mocks.onRequest : undefined,
    isRequesting: false,
    abort: vi.fn(),
  }),
}));

vi.mock("../../../src/features/chat/components/usePipelineActions", () => ({
  usePipelineActions: () => ({
    handlePipelineConfirm: vi.fn(),
    handleLocalUploadSubmit: vi.fn(),
    isPipelineSubmitting: false,
  }),
}));

vi.mock("../../../src/features/chat/components/useBubbleItems", () => ({
  useBubbleItems: () => [],
}));

vi.mock("../../../src/features/chat/components/useSessionUIState", () => ({
  useSessionUIState: () => ({
    activeForm: null,
    activeFormSlots: null,
    activeUploadFile: null,
    dispatchedActions: new Set(),
    pipelineStatus: null,
    setActiveForm: vi.fn(),
    setActiveFormSlots: vi.fn(),
    setActiveUploadFile: vi.fn(),
    openUploadFormForSession: vi.fn(),
    setPipelineStatus: vi.fn(),
    setDispatchedActions: vi.fn(),
    clearSessionUI: vi.fn(),
  }),
}));

vi.mock("../../../src/features/chat/components/useSessionConversations", async () => {
  const React = await import("react");
  return {
    useSessionConversations: () => {
      const [activeConversationKey, setActiveConversationKey] =
        React.useState("");
      return {
        isCreating: false,
        conversations: [],
        activeConversationKey,
        handleActiveConversationChange: setActiveConversationKey,
        createAndActivateSession: async () => {
          const sessionId = await mocks.createAndActivateSession();
          setActiveConversationKey(sessionId);
          return sessionId;
        },
        refreshSessionTitle: mocks.refreshSessionTitle,
        handleCreateSession: vi.fn(),
        conversationsMenu: vi.fn(),
      };
    },
  };
});

vi.mock("@ant-design/x", async () => {
  const React = await import("react");
  const Sender = React.forwardRef(
    (
      props: {
        onSubmit?: (value: string) => void;
      },
      ref: React.Ref<{ clear: () => void }>,
    ) => {
      React.useImperativeHandle(ref, () => ({ clear: vi.fn() }));
      return (
        <button
          aria-label="send test message"
          type="button"
          onClick={() => props.onSubmit?.("Hello from test")}
        >
          Send
        </button>
      );
    },
  );
  Sender.displayName = "MockSender";

  return {
    XProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Bubble: { List: () => <div data-testid="bubble-list" /> },
    Sender,
    Conversations: () => <nav data-testid="conversations" />,
  };
});

vi.mock("antd", async (importOriginal) => {
  const actual = await importOriginal<typeof import("antd")>();
  return {
    ...actual,
    App: {
      ...actual.App,
      useApp: () => ({
        message: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
      }),
    },
  };
});

beforeEach(() => {
  mocks.createAndActivateSession.mockResolvedValue("new-session");
  mocks.sendChatMessage.mockResolvedValue(undefined);
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    window.setTimeout(() => callback(performance.now()), 0);
    return 1;
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("ChatView", () => {
  it("shows the conversation list by default even with a stale collapse preference", () => {
    window.localStorage.setItem("chat.convCollapsed", "1");

    render(<ChatView />);

    expect(screen.getByTestId("conversations").parentElement).toHaveStyle({
      width: "240px",
    });
  });

  it("starts SSE with the latest onRequest after creating the first session", async () => {
    render(<ChatView />);

    fireEvent.click(screen.getByRole("button", { name: /send test message/i }));

    await waitFor(() => {
      expect(mocks.sendChatMessage).toHaveBeenCalledWith(
        "new-session",
        "Hello from test",
      );
    });
    await waitFor(() => {
      expect(mocks.onRequest).toHaveBeenCalledWith({
        messages: [{ role: "user", content: "Hello from test" }],
      });
    });
    expect(mocks.refreshSessionTitle).toHaveBeenCalledWith("new-session");
  });
});
