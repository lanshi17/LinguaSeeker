import { useMemo } from "react";
import type { BubbleItemType } from "@ant-design/x";
import type { MessageInfo } from "@ant-design/x-sdk/es/x-chat";
import type { ChatAction } from "../types/actions";
import type { ChatBubbleMessage } from "../utils/messageHistory";
import { toUniqueChatMessageKeys } from "../utils/messageHistory";
import { ChatMarkdown } from "../utils/markdown";
import { ChatActionBubble } from "./ChatActionBubble";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { PipelineSummaryCard, PipelineStatusCard } from "./forms";
import type { PipelineSummarySlots } from "./forms";
import type { PerSessionUIState } from "./chatConfig";
import { WelcomeBlock, type WelcomeAction } from "./WelcomeBlock";

interface UseBubbleItemsParams {
  messages: MessageInfo<ChatBubbleMessage>[];
  activeForm: PerSessionUIState["activeForm"];
  activeFormSlots: PerSessionUIState["activeFormSlots"];
  pipelineStatus: PerSessionUIState["pipelineStatus"];
  isRequesting: boolean;
  dispatchedActions: Set<string>;
  handleDispatchAction: (action: ChatAction, key?: string) => void;
  handlePipelineConfirm: (slots: PipelineSummarySlots) => void;
  handleWelcomeAction: (action: WelcomeAction) => void;
  setActiveForm: (intent: PerSessionUIState["activeForm"]) => void;
  setActiveFormSlots: (slots: PerSessionUIState["activeFormSlots"]) => void;
}

/**
 * Builds the Bubble.List items array from chat messages, adding
 * contentRender for assistant messages (markdown, action bubbles,
 * thinking indicator, streaming cursor) and synthetic items for
 * pipeline confirm form, pipeline status card, and welcome block.
 */
export function useBubbleItems(params: UseBubbleItemsParams): BubbleItemType[] {
  const {
    messages,
    activeForm,
    activeFormSlots,
    pipelineStatus,
    isRequesting,
    dispatchedActions,
    handleDispatchAction,
    handlePipelineConfirm,
    handleWelcomeAction,
    setActiveForm,
    setActiveFormSlots,
  } = params;

  return useMemo(() => {
    const messageKeys = toUniqueChatMessageKeys(messages);
    const items: BubbleItemType[] = messages.map(({ id, message, status }, index) => {
      const messageKey = messageKeys[index];
      const action = (message as { action?: ChatAction }).action;
      const dispatchKey = `${id ?? messageKey}`;

      const renderAssistant = (content: string) => {
        const isLoadingEmpty =
          (status === "loading" || status === "updating") && !content;
        const isStreaming =
          !isLoadingEmpty &&
          (status === "loading" || status === "updating") &&
          Boolean(content);

        if (isLoadingEmpty) {
          return (
            <ThinkingIndicator
              hints={[
                "Reading your message",
                "Retrieving relevant literature",
                "Reasoning over the evidence",
                "Drafting a grounded reply",
              ]}
            />
          );
        }

        return (
          <div className={isStreaming ? "chat-streaming-cursor" : ""}>
            <ChatMarkdown source={content} />
            {action ? (
              <ChatActionBubble
                action={action}
                dispatched={dispatchedActions.has(dispatchKey)}
                onDispatch={(payload) =>
                  handleDispatchAction(payload, dispatchKey)
                }
              />
            ) : null}
          </div>
        );
      };

      return {
        key: messageKey,
        role: message.role,
        content: message.content,
        streaming: false, // we render our own cursor via chat-streaming-cursor
        loading: false, // we render our own ThinkingIndicator via contentRender
        ...(message.role === "assistant"
          ? { contentRender: renderAssistant }
          : {}),
      };
    });

    if (activeForm === "confirm-pipeline") {
      items.push({
        key: "__confirm__",
        role: "assistant",
        content: "",
        variant: "borderless" as const,
        contentRender: () => (
          <PipelineSummaryCard
            key={`summary:${JSON.stringify(activeFormSlots)}`}
            slots={(activeFormSlots ?? {}) as PipelineSummarySlots}
            onConfirm={handlePipelineConfirm}
            onModify={() => {
              setActiveForm(null);
              setActiveFormSlots(null);
            }}
            isSubmitting={isRequesting}
          />
        ),
      });
    }

    if (pipelineStatus) {
      items.push({
        key: "__status__",
        role: "assistant",
        content: "",
        variant: "borderless" as const,
        contentRender: () => (
          <PipelineStatusCard
            runId={pipelineStatus.runId}
            status={pipelineStatus.status}
            phases={pipelineStatus.phases}
          />
        ),
      });
    }

    if (items.length === 0) {
      items.unshift({
        key: "__welcome__",
        role: "assistant",
        content: "",
        variant: "borderless" as const,
        contentRender: () => (
          <WelcomeBlock onPick={handleWelcomeAction} />
        ),
      });
    }

    return items;
  }, [
    messages,
    activeForm,
    activeFormSlots,
    pipelineStatus,
    isRequesting,
    handlePipelineConfirm,
    handleWelcomeAction,
    dispatchedActions,
    handleDispatchAction,
    setActiveForm,
    setActiveFormSlots,
  ]);
}
