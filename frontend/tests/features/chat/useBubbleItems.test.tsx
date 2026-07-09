import "@testing-library/jest-dom/vitest";

import type React from "react";
import { cleanup, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BubbleItemType } from "@ant-design/x";
import type { MessageInfo } from "@ant-design/x-sdk/es/x-chat";

import { useBubbleItems } from "../../../src/features/chat/components/useBubbleItems";
import type { ChatBubbleMessage } from "../../../src/features/chat/utils/messageHistory";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function messageInfo(
  role: ChatBubbleMessage["role"],
  content: string,
  status = "success",
): MessageInfo<ChatBubbleMessage> {
  return {
    id: `${role}:${content}`,
    message: { role, content },
    status,
  } as MessageInfo<ChatBubbleMessage>;
}

function renderContent(item: BubbleItemType, content: string) {
  const renderItemContent = item.contentRender as
    | ((value: string) => React.ReactNode)
    | undefined;

  render(<>{renderItemContent?.(content)}</>);
}

describe("useBubbleItems", () => {
  it("adds follow-up suggestions to the last completed assistant reply", () => {
    const { result } = renderHook(() =>
      useBubbleItems({
        messages: [
          messageInfo("user", "What does this mean?"),
          messageInfo("assistant", "The evidence summary is ready."),
        ],
        activeForm: null,
        activeFormSlots: null,
        activeUploadFile: null,
        pipelineStatus: null,
        isRequesting: false,
        isPreparingResponse: false,
        isPipelineSubmitting: false,
        dispatchedActions: new Set<string>(),
        handleDispatchAction: vi.fn(),
        handlePipelineConfirm: vi.fn(),
        handleLocalUploadSubmit: vi.fn(),
        handleWelcomeAction: vi.fn(),
        setActiveForm: vi.fn(),
        setActiveFormSlots: vi.fn(),
      }),
    );

    expect(result.current[2]).toEqual(
      expect.objectContaining({
        key: "__followups__",
        role: "assistant",
        variant: "borderless",
        className: "cv-followups-bubble",
        avatar: null,
      }),
    );
    renderContent(result.current[2], "");

    expect(screen.getByText("Suggested next questions")).toHaveClass(
      "cv-followups-label",
    );
    expect(
      screen.getByRole("button", {
        name: "Which evidence gaps should I resolve next?",
      }),
    ).toBeInTheDocument();
  });

  it("does not add follow-up suggestions while the last assistant reply is streaming", () => {
    const { result } = renderHook(() =>
      useBubbleItems({
        messages: [
          messageInfo("user", "What does this mean?"),
          messageInfo("assistant", "Partial answer", "updating"),
        ],
        activeForm: null,
        activeFormSlots: null,
        activeUploadFile: null,
        pipelineStatus: null,
        isRequesting: true,
        isPreparingResponse: false,
        isPipelineSubmitting: false,
        dispatchedActions: new Set<string>(),
        handleDispatchAction: vi.fn(),
        handlePipelineConfirm: vi.fn(),
        handleLocalUploadSubmit: vi.fn(),
        handleWelcomeAction: vi.fn(),
        setActiveForm: vi.fn(),
        setActiveFormSlots: vi.fn(),
      }),
    );

    expect(
      result.current.some((item) => item.key === "__followups__"),
    ).toBe(false);
  });
});
