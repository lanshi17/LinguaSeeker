import { useCallback, useEffect, useRef, useState } from "react";
import { XProvider, Bubble, Sender, Conversations } from "@ant-design/x";
import type { SenderRef } from "@ant-design/x/es/sender/interface";
import { message as antdMessage } from "antd";
import { ListChecks } from "lucide-react";
import { TaskQueuePanel } from "@/features/pipeline";
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

// ─── Main ChatView ─────────────────────────────────────────────────────

export function ChatView({ processingRunId, sessionId }: ChatViewProps) {
  if (sessionId) {
    return <SingleSessionChat sessionId={sessionId} />;
  }
  return <FullChatView processingRunId={processingRunId} />;
}

// ─── Full Chat View ────────────────────────────────────────────────────

function FullChatView({ processingRunId }: { processingRunId?: string }) {
  // The hook below reads localStorage in its initial state, which differs
  // from the SSR render and would trip React's hydration check. We render
  // a stable placeholder first, then flip `mounted` in an effect to show
  // the real sidebar. Pattern: https://nextjs.org/docs/app/building-your-application/rendering/composition-patterns
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true); // eslint-disable-line react-hooks/set-state-in-effect -- standard Next.js SSR/CSR hydration gate; the one-shot mount flag has no cascading-render risk because the dep array is empty.
  }, []);

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
        window.location.href = qs ? `/evidence?${qs}` : "/evidence";
        return;
      }

      if (action.intent === "review-changes") {
        const filter = action.slots?.filter ?? "all";
        window.location.href = `/evidence?review_status=${filter ?? "all"}`;
        return;
      }

      if (action.intent === "check-pipeline-status") {
        const runId = action.slots?.run_id;
        window.location.href = runId ? `/pipeline/${runId}` : "/pipeline";
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
        antdMessage.info(
          "Describe what you want to run — I'll ask the right questions.",
        );
        return;
      }

      antdMessage.info(
        `${action.intent} is recognised but its dedicated form is not implemented yet.`,
      );
    },
    [setActiveForm, setActiveFormSlots, setDispatchedActions],
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
      } catch {
        antdMessage.error("Failed to send message");
      }
    },
    [
      activeConversationKey,
      captureFirstMessageLabel,
      createAndActivateSession,
      onRequest,
      setActiveForm,
      setActiveFormSlots,
    ],
  );

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
    handleSendMessage,
    setActiveForm,
    setActiveFormSlots,
  });

  // Sender ref: lets us clear the input after a successful send.
  const senderRef = useRef<SenderRef>(null);
  const handleSubmitAndClear = useCallback(
    (content: string) => {
      void handleSendMessage(content).finally(() => {
        // Clear unconditionally so a failed send still resets the UI
        // (the error is surfaced via antdMessage in the catch branch).
        senderRef.current?.clear();
      });
    },
    [handleSendMessage],
  );

  return (
    <XProvider>
      <style>{`
        .cv-tq-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          border-radius: 6px;
          padding: 4px 8px;
          font-size: 11.5px;
          font-weight: 500;
          transition: color 150ms, background-color 150ms;
          border: none;
          background: none;
          cursor: pointer;
        }
        .cv-tq-btn:focus-visible {
          outline: 2px solid var(--color-primary-600, #0891b2);
          outline-offset: 2px;
        }
      `}</style>
      <div style={{ display: "flex", height: "100%", overflow: "hidden", backgroundColor: "#fff" }}>
        {/* Conversation sidebar — gated on `mounted` to keep SSR HTML
            identical to the first client render (see hydration comment
            above). The placeholder reserves the 240px column so the
            main chat area doesn't shift when the real sidebar mounts. */}
        {mounted ? (
          <Conversations
            style={{ width: 240, borderRight: "1px solid #f0f0f0" }}
            items={conversations}
            activeKey={activeConversationKey}
            onActiveChange={handleActiveConversationChange}
            menu={conversationsMenu}
            creation={{
              onClick: handleCreateSession,
              disabled: isCreating,
            }}
          />
        ) : (
          <div
            style={{ width: 240, borderRight: "1px solid #f0f0f0" }}
            aria-hidden="true"
          />
        )}

        {/* Main chat area */}
        <div style={{ display: "flex", minWidth: 0, flex: 1, flexDirection: "column" }}>
          {/* Task-queue toolbar: a slim bar above the bubble stream so the
              user can collapse/expand the right-side queue without losing
              chat scroll position. */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              borderBottom: "1px solid #f3f4f6",
              padding: "6px 16px",
            }}
          >
            <button
              type="button"
              onClick={toggleTaskQueue}
              aria-pressed={taskQueueOpen}
              aria-label={
                taskQueueOpen ? "Hide task queue" : "Show task queue"
              }
              className="cv-tq-btn"
              style={
                taskQueueOpen
                  ? { backgroundColor: "#111827", color: "#fff", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }
                  : { color: "#6b7280" }
              }
              onMouseEnter={(e) => {
                if (!taskQueueOpen) {
                  e.currentTarget.style.backgroundColor = "#f3f4f6";
                  e.currentTarget.style.color = "#1f2937";
                }
              }}
              onMouseLeave={(e) => {
                if (!taskQueueOpen) {
                  e.currentTarget.style.backgroundColor = "";
                  e.currentTarget.style.color = "#6b7280";
                }
              }}
            >
              <ListChecks style={{ width: 14, height: 14 }} aria-hidden />
              <span>Task Queue</span>
            </button>
            <span style={{ fontSize: 10.5, color: "#9ca3af" }}>
              {taskQueueOpen ? "Pinned on the right" : "Hidden"}
            </span>
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
                style={{ borderTop: "1px solid #f3f4f6", padding: 16 }}
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
                placeholder="Ask the Lingua Seeker Agent..."
              />
            </div>

            {taskQueueOpen && <TaskQueuePanel onClose={toggleTaskQueue} />}
          </div>
        </div>
      </div>
    </XProvider>
  );
}
