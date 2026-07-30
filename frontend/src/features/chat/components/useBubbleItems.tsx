import { useMemo } from "react";
import type { BubbleItemType } from "@ant-design/x";
import type { MessageInfo } from "@ant-design/x-sdk/es/x-chat";
import { useI18n } from "@/lib/i18n";
import type { ChatAction } from "../types/actions";
import type { ChatBubbleMessage } from "../utils/messageHistory";
import { toUniqueChatMessageKeys } from "../utils/messageHistory";
import { ChatMarkdown } from "../utils/markdown";
import { ChatActionBubble } from "./ChatActionBubble";
import { ChatGraphResultCard } from "./ChatGraphResultCard";
import { ThinkingIndicator } from "./ThinkingIndicator";
import {
  ChatUploadTaskCard,
  PipelineSummaryCard,
  PipelineStatusCard,
} from "./forms";
import type { PipelineSummarySlots } from "./forms";
import type { PerSessionUIState } from "./chatConfig";
import { WelcomeBlock, type WelcomeAction } from "./WelcomeBlock";

/** State for rendering follow-up suggestions outside the bubble list. */
export interface FollowUpState {
  show: boolean;
  lastAssistantContent: string;
}

interface UseBubbleItemsParams {
  messages: MessageInfo<ChatBubbleMessage>[];
  activeForm: PerSessionUIState["activeForm"];
  activeFormSlots: PerSessionUIState["activeFormSlots"];
  activeUploadFile: PerSessionUIState["activeUploadFile"];
  pipelineStatus: PerSessionUIState["pipelineStatus"];
  graphResult: PerSessionUIState["graphResult"];
  isRequesting: boolean;
  isPreparingResponse: boolean;
  isPipelineSubmitting: boolean;
  dispatchedActions: Set<string>;
  handleDispatchAction: (action: ChatAction, key?: string) => void;
  handlePipelineConfirm: (slots: PipelineSummarySlots) => void;
  handleLocalUploadSubmit: (slots: PipelineSummarySlots, file: File) => void;
  handleWelcomeAction: (action: WelcomeAction) => void;
  setActiveForm: (intent: PerSessionUIState["activeForm"]) => void;
  setActiveFormSlots: (slots: PerSessionUIState["activeFormSlots"]) => void;
}

/**
 * Builds the Bubble.List items array from chat messages, adding
 * contentRender for assistant messages (markdown, action bubbles,
 * thinking indicator, streaming cursor) and synthetic items for
 * pipeline confirm form, pipeline status card, and welcome block.
 *
 * Also returns follow-up state so the caller can render
 * {@link FollowUpSuggestions} above the input sender.
 */
export function useBubbleItems(params: UseBubbleItemsParams): { items: BubbleItemType[]; followUp: FollowUpState } {
  const { t } = useI18n();
  const {
    messages,
    activeForm,
    activeFormSlots,
    activeUploadFile,
    pipelineStatus,
    graphResult,
    isRequesting,
    isPreparingResponse,
    isPipelineSubmitting,
    dispatchedActions,
    handleDispatchAction,
    handlePipelineConfirm,
    handleLocalUploadSubmit,
    handleWelcomeAction,
    setActiveForm,
    setActiveFormSlots,
  } = params;

  return useMemo(() => {
    const messageKeys = toUniqueChatMessageKeys(messages);
    const lastMessageIndex = messages.length - 1;
    const lastMessage = messages[lastMessageIndex];
    const lastCompletedAssistantIndex =
      lastMessage?.message.role === "assistant" &&
      lastMessage.message.content.trim() &&
      lastMessage.status !== "loading" &&
      lastMessage.status !== "updating"
        ? lastMessageIndex
        : -1;
    const shouldShowFollowUps =
      lastCompletedAssistantIndex >= 0 &&
      !activeForm &&
      !pipelineStatus &&
      !isRequesting &&
      !isPreparingResponse;

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
          <div className={isStreaming ? "chat-streaming-cursor" : undefined}>
            <ChatMarkdown source={content} />
            {action && action.intent !== "graph-qa" ? (
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

    if (isPreparingResponse && !isRequesting) {
      items.push({
        key: "__preparing_response__",
        role: "assistant",
        content: "",
        contentRender: () => (
          <ThinkingIndicator
            label={t("chat.thinking.connectingLabel")}
            hints={[
              t("chat.thinking.saving"),
              t("chat.thinking.openingStream"),
            ]}
          />
        ),
      });
    }

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
            isSubmitting={isRequesting || isPipelineSubmitting}
          />
        ),
      });
    }

    if (activeForm === "upload-pdf") {
      items.push({
        key: "__upload__",
        role: "assistant",
        content: "",
        variant: "borderless" as const,
        contentRender: () => (
          <ChatUploadTaskCard
            key={`upload:${activeUploadFile?.name ?? "empty"}:${JSON.stringify(activeFormSlots)}`}
            slots={(activeFormSlots ?? { source_type: "local" }) as PipelineSummarySlots}
            initialFile={activeUploadFile}
            onSubmit={handleLocalUploadSubmit}
            onCancel={() => {
              setActiveForm(null);
              setActiveFormSlots(null);
            }}
            isSubmitting={isPipelineSubmitting}
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

    if (graphResult) {
      items.push({
        key: "__graph__",
        role: "assistant",
        content: "",
        variant: "borderless" as const,
        contentRender: () => (
          <ChatGraphResultCard
            question={graphResult.question}
            status={graphResult.status}
            answer={graphResult.answer}
            subgraph={graphResult.subgraph}
            error={graphResult.error}
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

    const followUp: FollowUpState = {
      show: shouldShowFollowUps,
      lastAssistantContent:
        shouldShowFollowUps && lastCompletedAssistantIndex >= 0
          ? messages[lastCompletedAssistantIndex].message.content
          : "",
    };

    return { items, followUp };
  }, [
    messages,
    activeForm,
    activeFormSlots,
    activeUploadFile,
    pipelineStatus,
    graphResult,
    isRequesting,
    isPreparingResponse,
    isPipelineSubmitting,
    t,
    handlePipelineConfirm,
    handleLocalUploadSubmit,
    handleWelcomeAction,
    dispatchedActions,
    handleDispatchAction,
    setActiveForm,
    setActiveFormSlots,
  ]);
}
