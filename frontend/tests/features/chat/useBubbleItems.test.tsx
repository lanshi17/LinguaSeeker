import "@testing-library/jest-dom/vitest";

import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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

describe("useBubbleItems", () => {
  it("returns follow-up state for the last completed assistant reply", () => {
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

    expect(result.current.items).toHaveLength(2);
    expect(result.current.followUp).toEqual(
      expect.objectContaining({
        show: true,
        lastAssistantContent: "The evidence summary is ready.",
      }),
    );
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

    expect(result.current.items.some((item) => item.key === "__followups__")).toBe(false);
    expect(result.current.followUp.show).toBe(false);
  });
});
