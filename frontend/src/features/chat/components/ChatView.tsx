import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { XProvider, Bubble, Sender, Conversations } from "@ant-design/x";
import type { SenderRef } from "@ant-design/x/es/sender/interface";
import { App } from "antd";
import { ListChecks, ChevronLeft, ChevronRight } from "lucide-react";
import { TaskQueuePanel } from "@/features/pipeline";
import { useI18n } from "@/lib/i18n";
import { extractErrorMessage } from "@/lib/api/error";
import type { ChatAction } from "../types/actions";
import { sendChatMessage } from "../providers/acmgChatProvider";
import {
  type ChatViewProps,
  readInitialQueueOpen,
  roles,
} from "./chatConfig";
import { SingleSessionChat } from "./SingleSessionChat";
import { useChatProvider } from "./useChatProvider";
import { useSessionConversations } from "./useSessionConversations";
import { useBubbleItems } from "./useBubbleItems";
import { usePipelineActions } from "./usePipelineActions";
import { useSessionUIState } from "./useSessionUIState";
import type { WelcomeAction } from "./WelcomeBlock";

// ─── Main ChatView ─────────────────────────────────────────────────────

export function ChatView({ processingRunId, sessionId }: ChatViewProps) {
  if (sessionId) {
    return <SingleSessionChat sessionId={sessionId} />;
  }
  return <FullChatView processingRunId={processingRunId} />;
}

// ─── Full Chat View ────────────────────────────────────────────────────

function FullChatView({ processingRunId }: { processingRunId?: string }) {
  const { t } = useI18n();
  const { message } = App.useApp();
  const navigate = useNavigate();

  const [taskQueueOpen, setTaskQueueOpen] = useState<boolean>(
    readInitialQueueOpen,
  );
  const toggleTaskQueue = useCallback(() => {
    setTaskQueueOpen((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(
          "chat.taskQueueOpen",
          next ? "1" : "0",
        );
      } catch {
        // Storage quota or sandboxed env — silently ignore.
      }
      return next;
    });
  }, []);

  const [convCollapsed, setConvCollapsed] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem("chat.convCollapsed") === "1";
    } catch {
      return false;
    }
  });
  const toggleConv = useCallback(() => {
    setConvCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem("chat.convCollapsed", next ? "1" : "0");
      } catch {
        // noop
      }
      return next;
    });
  }, []);

  // ── Session & conversation management ──
  // clearSessionUI is called asynchronously inside Modal.confirm's onOk,
  // so a mutable ref breaks the circular dependency with activeConversationKey.
  const clearSessionUIRef = useRef<(id: string) => void>(() => {});

  const {
    isCreating,
    conversations,
    activeConversationKey,
    handleActiveConversationChange,
    createAndActivateSession,
    captureFirstMessageLabel,
    handleCreateSession,
    conversationsMenu,
  } = useSessionConversations(processingRunId, clearSessionUIRef);

  // ── Provider & message hydration ──
  const { activeProvider, messages, onRequest, isRequesting, abort } =
    useChatProvider(activeConversationKey);

  // ── Per-session ephemeral UI state ──
  const {
    activeForm,
    activeFormSlots,
    dispatchedActions,
    pipelineStatus,
    setActiveForm,
    setActiveFormSlots,
    setPipelineStatus,
    setDispatchedActions,
    clearSessionUI,
  } = useSessionUIState(activeConversationKey);

  // Keep the ref in sync so the Modal.confirm onOk always calls the
  // latest clearSessionUI (stable from useState, but good hygiene).
  clearSessionUIRef.current = clearSessionUI;

  const handleDispatchAction = useCallback(
    (action: ChatAction, key?: string) => {
      if (key) {
        setDispatchedActions((prev) => {
          if (prev.has(key)) return prev;
          const next = new Set(prev);
          next.add(key);
          return next;
        });
      }

      if (action.intent === "search-evidence") {
        const params = new URLSearchParams();
        for (const [slot, value] of Object.entries(action.slots ?? {})) {
          if (value) params.set(slot, value);
        }
        const qs = params.toString();
        navigate(qs ? `/evidence?${qs}` : "/evidence");
        return;
      }

      if (action.intent === "review-changes") {
        const filter = action.slots?.filter ?? "all";
        navigate(`/evidence?review_status=${filter ?? "all"}`);
        return;
      }

      if (action.intent === "check-pipeline-status") {
        const runId = action.slots?.run_id;
        navigate(runId ? `/pipeline/${runId}` : "/pipeline");
        return;
      }

      if (action.intent === "confirm-pipeline") {
        setActiveForm("confirm-pipeline");
        setActiveFormSlots(action.slots ?? {});
        return;
      }

      if (action.intent === "start-pipeline" || action.intent === "upload-pdf") {
        // Legacy intents — the chat no longer opens inline forms. Nudge the
        // user toward the conversational flow; the LLM will drive slot
        // gathering from here and eventually dispatch `confirm-pipeline`.
        message.info(
          "Describe what you want to run — I'll ask the right questions.",
        );
        return;
      }

      message.info(
        `${action.intent} is recognised but its dedicated form is not implemented yet.`,
      );
    },
    [message, navigate, setActiveForm, setActiveFormSlots, setDispatchedActions],
  );

  // ── Send message: create session if needed, POST to persist, then stream AI reply ──
  //
  // NOTE: We use onRequest from useXChat (not provider.request directly)
  // because onRequest also manages local message state (user bubble,
  // loading indicator, streaming updates). The double-rAF ensures the
  // React state update from createAndActivateSession has committed and
  // the derived `activeProvider` points at the new session's provider
  // before onRequest dispatches the SSE stream.
  const handleSendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;

      setActiveForm(null);
      setActiveFormSlots(null);

      try {
        let sessionKey = activeConversationKey;
        if (!sessionKey) {
          sessionKey = await createAndActivateSession();
          // Wait for the provider re-render to commit.
          await new Promise<void>((resolve) => {
            requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
          });
        }

        await sendChatMessage(sessionKey, trimmed);
        captureFirstMessageLabel(sessionKey, trimmed);
        onRequest?.({ messages: [{ role: "user" as const, content: trimmed }] });
      } catch (err) {
        message.error(extractErrorMessage(err, "Failed to send message"));
      }
    },
    [
      activeConversationKey,
      captureFirstMessageLabel,
      createAndActivateSession,
      message,
      onRequest,
      setActiveForm,
      setActiveFormSlots,
    ],
  );

  const handleWelcomeAction = useCallback(
    (action: WelcomeAction) => {
      if (action.kind === "navigate") {
        navigate(action.to);
        return;
      }
      void handleSendMessage(action.message);
    },
    [handleSendMessage, navigate],
  );

  const handleNewChat = useCallback(() => {
    void (async () => {
      const sessionKey = await handleCreateSession();
      if (sessionKey) {
        clearSessionUI(sessionKey);
      }
    })();
  }, [clearSessionUI, handleCreateSession]);

  // ── Pipeline actions ──
  const { handlePipelineConfirm } = usePipelineActions({
    activeProvider,
    onRequest,
    setActiveForm,
    setPipelineStatus,
  });

  // ── Build bubble items ──
  const bubbleItems = useBubbleItems({
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
  });

  // Sender ref: lets us clear the input after a successful send.
  const senderRef = useRef<SenderRef>(null);
  const handleSubmitAndClear = useCallback(
    (content: string) => {
      void handleSendMessage(content).finally(() => {
        // Clear unconditionally so a failed send still resets the UI
        // (the error is surfaced via message in the catch branch).
        senderRef.current?.clear();
      });
    },
    [handleSendMessage],
  );


  return (
    <XProvider>
      <div style={{ display: "flex", height: "100%", overflow: "hidden", backgroundColor: "var(--color-surface)" }}>
        {/* Conversation list (clipped) */}
        <div
          style={{
            width: convCollapsed ? 0 : 240,
            overflow: "hidden",
            transition: "width 200ms ease",
            height: "100%",
            flexShrink: 0,
          }}
        >
          <Conversations
            style={{ width: 240 }}
            items={conversations}
            activeKey={activeConversationKey}
            onActiveChange={handleActiveConversationChange}
            menu={conversationsMenu}
            creation={{
              onClick: handleNewChat,
              disabled: isCreating,
            }}
          />
        </div>

        {/* Toggle — flex item, never clipped */}
        <button
          type="button"
          onClick={toggleConv}
          aria-label={convCollapsed ? t("chat.expandConversations") : t("chat.collapseConversations")}
          className="cv-conv-toggle"
          data-collapsed={convCollapsed}
        >
          {convCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>

        {/* Main chat area */}
        <div style={{ display: "flex", minWidth: 0, flex: 1, flexDirection: "column" }}>
          {/* Task-queue toolbar: a slim bar above the bubble stream so the
              user can collapse/expand the right-side queue without losing
              chat scroll position. */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: 8,
              borderBottom: "1px solid var(--color-bg-muted)",
              padding: "6px 16px",
            }}
          >
            <button
              type="button"
              onClick={toggleTaskQueue}
              aria-pressed={taskQueueOpen}
              aria-label={
                taskQueueOpen ? t("chat.hideTaskQueue") : t("chat.showTaskQueue")
              }
              className="cv-tq-btn"
              style={
                taskQueueOpen
                  ? { backgroundColor: "var(--color-text)", color: "var(--color-surface)", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }
                  : { color: "var(--color-text-secondary)" }
              }
              onMouseEnter={(e) => {
                if (!taskQueueOpen) {
                  e.currentTarget.style.backgroundColor = "var(--color-bg-muted)";
                  e.currentTarget.style.color = "var(--color-code-text)";
                }
              }}
              onMouseLeave={(e) => {
                if (!taskQueueOpen) {
                  e.currentTarget.style.backgroundColor = "";
                  e.currentTarget.style.color = "var(--color-text-secondary)";
                }
              }}
            >
              <ListChecks style={{ width: 14, height: 14 }} aria-hidden />
              <span>{t("chat.taskQueue")}</span>
            </button>
          </div>

          <div style={{ display: "flex", minHeight: 0, flex: 1 }}>
            <div style={{ display: "flex", minWidth: 0, flex: 1, flexDirection: "column" }}>
              <Bubble.List
                style={{ flex: 1, overflow: "auto", padding: 16 }}
                items={bubbleItems}
                role={roles}
                autoScroll
              />
              <Sender
                ref={senderRef}
                style={{ borderTop: "1px solid var(--color-bg-muted)", padding: 16 }}
                loading={isRequesting}
                onCancel={() => {
                  // Cancel via the provider's own AbortController for
                  // reliable fetch termination. Also try the SDK's
                  // abort as a secondary cleanup for internal state.
                  try {
                    activeProvider?.abort();
                  } catch {
                    // noop
                  }
                  try {
                    abort?.();
                  } catch {
                    // noop
                  }
                }}
                onSubmit={handleSubmitAndClear}
                placeholder={t("chat.agentPlaceholder")}
              />
            </div>

            {taskQueueOpen && <TaskQueuePanel onClose={toggleTaskQueue} />}
          </div>
        </div>
      </div>
    </XProvider>
  );
}
