"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  XProvider,
  Bubble,
  Sender,
  Conversations,
} from "@ant-design/x";
import type { SenderRef } from "@ant-design/x/es/sender/interface";
import { useXChat, useXConversations } from "@ant-design/x-sdk";
import type { MessageInfo } from "@ant-design/x-sdk/es/x-chat";
import { RobotOutlined, UserOutlined, DeleteOutlined } from "@ant-design/icons";
import { Avatar, Modal, message as antdMessage } from "antd";
import {
  createAcmgChatProvider,
  sendChatMessage,
} from "../providers/acmgChatProvider";
import { useChatSessions } from "../hooks/useChatSessions";
import { listMessages } from "../services/chat";
import {
  loadActiveChatSession,
  rememberActiveChatSession,
  upsertLocalChatSession,
} from "../utils/localSessions";
import {
  toUniqueChatMessageKeys,
  toXChatDefaultMessages,
  type ChatBubbleMessage,
} from "../utils/messageHistory";
import { clearCachedMessageStore } from "../utils/messageStore";
import type { ChatAction, ChatActionIntent } from "../types/actions";
import { ChatMarkdown } from "../utils/markdown";
import { PipelineStartForm, PipelineStatusCard } from "./forms";
import type { PipelineFormData } from "./forms";
import { ChatActionBubble } from "./ChatActionBubble";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { apiClient } from "@/lib/api/client";
import { extractErrorMessage } from "@/lib/api/error";
import {
  BookOpen,
  FlaskConical,
  Search,
  Sparkles,
  Upload,
} from "lucide-react";

/** Max words of the first user message used as the session title. */
const SESSION_TITLE_WORDS = 5;

interface ChatViewProps {
  processingRunId?: string;
  sessionId?: string;
}

// ─── Role config for Bubble.List ───────────────────────────────────────

const roles = {
  assistant: {
    placement: "start" as const,
    avatar: (
      <Avatar icon={<RobotOutlined />} style={{ backgroundColor: "#0891b2" }} />
    ),
  },
  user: {
    placement: "end" as const,
    avatar: (
      <Avatar icon={<UserOutlined />} style={{ backgroundColor: "#22c55e" }} />
    ),
  },
};

// ─── Default welcome message shown when chat is empty ───────────────────

interface SuggestionChip {
  icon: React.ReactNode;
  title: string;
  description: string;
  /** Message content sent when the chip is clicked. */
  message: string;
  accent: string; // tailwind bg class (light)
  accentText: string; // tailwind text class
}

const SUGGESTIONS: SuggestionChip[] = [
  {
    icon: <FlaskConical className="h-4 w-4" />,
    title: "Run the pipeline",
    description: "Ingest a paper via PMID, DOI, or keyword",
    message: "Run the four-phase pipeline on PMID 34521984",
    accent: "bg-cyan-50",
    accentText: "text-cyan-600",
  },
  {
    icon: <Upload className="h-4 w-4" />,
    title: "Upload a PDF",
    description: "Parse, translate, and extract evidence",
    message: "I want to upload a PDF",
    accent: "bg-violet-50",
    accentText: "text-violet-600",
  },
  {
    icon: <Search className="h-4 w-4" />,
    title: "Search evidence",
    description: "Query extracted evidence by gene or variant",
    message: "Search the evidence database",
    accent: "bg-emerald-50",
    accentText: "text-emerald-600",
  },
  {
    icon: <BookOpen className="h-4 w-4" />,
    title: "Classify a variant",
    description: "Walk through ACMG/AMP 2015 criteria",
    message: "Help me classify a variant with ACMG criteria",
    accent: "bg-amber-50",
    accentText: "text-amber-600",
  },
];

interface WelcomeBlockProps {
  onPick?: (message: string) => void;
}

function WelcomeBlock({ onPick }: WelcomeBlockProps) {
  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 flex-none items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-sm">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="space-y-1.5">
          <h2 className="text-[15px] font-semibold tracking-tight text-gray-900">
            Welcome to <span className="text-cyan-600">Cross Evidence</span>
          </h2>
          <p className="text-[13.5px] leading-relaxed text-gray-600">
            A literature-grounded assistant for variant and evidence
            classification. I run a four-phase extraction pipeline and ground
            every claim in source coordinates.
          </p>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((chip) => {
          const isInteractive = Boolean(onPick);
          return (
            <button
              key={chip.title}
              type="button"
              onClick={() => onPick?.(chip.message)}
              disabled={!isInteractive}
              className={[
                "group flex items-start gap-3 rounded-xl border border-gray-100",
                "bg-white p-3 text-left transition-all duration-150",
                isInteractive
                  ? "cursor-pointer hover:-translate-y-0.5 hover:border-gray-200 hover:shadow-sm"
                  : "cursor-default",
              ].join(" ")}
            >
              <span
                className={`flex h-8 w-8 flex-none items-center justify-center rounded-lg ${chip.accent} ${chip.accentText}`}
              >
                {chip.icon}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-medium text-gray-900">
                  {chip.title}
                </span>
                <span className="mt-0.5 block truncate text-[12px] text-gray-500">
                  {chip.description}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <p className="border-t border-gray-100 pt-3 text-[11.5px] leading-relaxed text-gray-400">
        The agent does not provide clinical diagnoses. Outputs are research-grade
        evidence for review by qualified professionals.
      </p>
    </div>
  );
}

// ─── Per-session ephemeral UI state shape ──────────────────────────────

interface PerSessionUIState {
  activeForm: ChatActionIntent | null;
  activeFormSlots: ChatAction["slots"] | null;
  dispatchedActions: Set<string>;
  pipelineStatus: {
    runId: string;
    status: string;
    phases?: Record<
      string,
      { status: string; duration_seconds?: number | null }
    >;
  } | null;
}

/** Returns a fresh default state object. Uses a factory (not a constant)
 *  so that `dispatchedActions` is never shared across sessions. */
function createEmptySessionUI(): PerSessionUIState {
  return {
    activeForm: null,
    activeFormSlots: null,
    dispatchedActions: new Set<string>(),
    pipelineStatus: null,
  };
}

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

  const [providerCache] = useState(
    () => new Map<string, ReturnType<typeof createAcmgChatProvider>>(),
  );

  const getProvider = useCallback(
    (key: string) => {
      if (!providerCache.has(key)) {
        providerCache.set(key, createAcmgChatProvider(key));
      }
      return providerCache.get(key)!;
    },
    [providerCache],
  );

  const { sessions, createSession, isCreating, removeSession } =
    useChatSessions(processingRunId);

  // Per-session title overrides: first user message's first
  // SESSION_TITLE_WORDS words. Default label used until then.
  const [sessionLabels, setSessionLabels] = useState<Record<string, string>>(
    {},
  );

  const conversationItems = useMemo(
    () =>
      sessions.map((s) => ({
        key: s.session_id,
        label: sessionLabels[s.session_id] ?? `Session ${s.session_id.slice(0, 8)}`,
      })),
    [sessions, sessionLabels],
  );

  const {
    conversations,
    activeConversationKey,
    setActiveConversationKey,
    addConversation,
    setConversations,
    removeConversation,
  } = useXConversations({
    defaultConversations: conversationItems,
    defaultActiveConversationKey: sessions[0]?.session_id,
  });

  const captureFirstMessageLabel = useCallback(
    (sessionKey: string, content: string) => {
      setSessionLabels((prev) => {
        if (prev[sessionKey]) return prev;
        const trimmed = content.trim();
        if (!trimmed) return prev;
        return { ...prev, [sessionKey]: trimmed.split(/\s+/).slice(0, SESSION_TITLE_WORDS).join(" ") };
      });
    },
    [],
  );

  const handleActiveConversationChange = useCallback(
    (key: string) => {
      setActiveConversationKey(key);
      if (!processingRunId) {
        rememberActiveChatSession(undefined, key);
      }
    },
    [processingRunId, setActiveConversationKey],
  );

  useEffect(() => {
    setConversations(conversationItems);

    const activeExists = conversationItems.some(
      (item) => item.key === activeConversationKey,
    );
    if (activeConversationKey && activeExists) {
      return;
    }

    const remembered = !processingRunId ? loadActiveChatSession() : null;
    const rememberedExists = conversationItems.some(
      (item) => item.key === remembered,
    );

    if (remembered && rememberedExists) {
      handleActiveConversationChange(remembered);
      return;
    }

    if (conversationItems[0]) {
      handleActiveConversationChange(conversationItems[0].key);
    }
  }, [
    activeConversationKey,
    conversationItems,
    handleActiveConversationChange,
    processingRunId,
    setConversations,
  ]);

  const activeProvider = activeConversationKey
    ? getProvider(activeConversationKey)
    : undefined;

  const xChat = useXChat({
    provider: activeProvider,
    conversationKey: activeConversationKey,
    defaultMessages: async () => [],
  });

  // useXChat should always return an object, but guard against
  // undefined to prevent "Cannot read properties of undefined" crashes.
  const messages = xChat?.messages ?? [];
  const onRequest = xChat?.onRequest;
  const isRequesting = xChat?.isRequesting ?? false;
  const abort = xChat?.abort;
  const setMessages = xChat?.setMessages;

  // Explicit, deterministic message hydration on session switch.
  // Runs on every `activeConversationKey` change — including the *second*
  // time we visit a session, where the SDK's cached store would otherwise
  // re-render stale bubbles until its async defaultMessages resolved.
  useEffect(() => {
    let cancelled = false;
    if (!activeConversationKey) {
      setMessages?.([]);
      return;
    }

    // Abort any in-flight SSE stream from the previous session so
    // its updateMessage calls don't write into the now-stale store.
    // Guarded on activeProvider *and* wrapped in try/catch: the SDK's
    // abort closure can throw when invoked during a provider transition
    // (the internal conversation lookup returns undefined mid-swap).
    if (activeProvider) {
      try {
        abort?.();
      } catch {
        // Swallow — the previous stream is already gone or the provider
        // is transitioning; either way there is nothing to abort.
      }
    }

    // Clear the visible list synchronously so no previous-session bubble
    // can flash while the network call is in flight.
    setMessages?.([]);

    listMessages(activeConversationKey)
      .then((history) => {
        if (cancelled) return;
        // toXChatDefaultMessages always provides `id`; cast past the
        // optional-id stub that DefaultMessageInfo uses.
        setMessages?.(
          toXChatDefaultMessages(history) as MessageInfo<ChatBubbleMessage>[],
        );
      })
      .catch(() => {
        if (cancelled) return;
        setMessages?.([]);
      });

    return () => {
      cancelled = true;
    };
    // activeProvider is derived from activeConversationKey + a stable cache
    // and is included so the provider-guard inside the effect never closes
    // over a stale (possibly undefined) provider reference.
  }, [abort, activeConversationKey, activeProvider, setMessages]);

  // ── Per-session ephemeral UI state ──
  const [sessionUI, setSessionUI] = useState<Record<string, PerSessionUIState>>(
    {},
  );

  const activeUI: PerSessionUIState = activeConversationKey
    ? (sessionUI[activeConversationKey] ?? createEmptySessionUI())
    : createEmptySessionUI();
  const { activeForm, activeFormSlots, dispatchedActions, pipelineStatus } =
    activeUI;

  const updateActiveUI = useCallback(
    (updater: (prev: PerSessionUIState) => PerSessionUIState) => {
      if (!activeConversationKey) return;
      const key = activeConversationKey;
      setSessionUI((prev) => ({
        ...prev,
        [key]: updater(prev[key] ?? createEmptySessionUI()),
      }));
    },
    [activeConversationKey],
  );

  const setActiveForm = useCallback(
    (intent: ChatActionIntent | null) =>
      updateActiveUI((p) => ({ ...p, activeForm: intent })),
    [updateActiveUI],
  );
  const setActiveFormSlots = useCallback(
    (slots: ChatAction["slots"] | null) =>
      updateActiveUI((p) => ({ ...p, activeFormSlots: slots })),
    [updateActiveUI],
  );
  const setPipelineStatus = useCallback(
    (
      status:
        | PerSessionUIState["pipelineStatus"]
        | ((
            prev: PerSessionUIState["pipelineStatus"],
          ) => PerSessionUIState["pipelineStatus"]),
    ) =>
      updateActiveUI((p) => ({
        ...p,
        pipelineStatus:
          typeof status === "function" ? status(p.pipelineStatus) : status,
      })),
    [updateActiveUI],
  );
  const setDispatchedActions = useCallback(
    (next: Set<string> | ((prev: Set<string>) => Set<string>)) =>
      updateActiveUI((p) => ({
        ...p,
        dispatchedActions:
          typeof next === "function" ? next(p.dispatchedActions) : next,
      })),
    [updateActiveUI],
  );

  const createAndActivateSession = useCallback(async (): Promise<string> => {
    const session = await createSession();
    const item = {
      key: session.session_id,
      label: `Session ${session.session_id.slice(0, 8)}`,
    };

    addConversation(item);
    handleActiveConversationChange(session.session_id);

    if (!processingRunId) {
      upsertLocalChatSession(undefined, session);
      rememberActiveChatSession(undefined, session.session_id);
    }

    return session.session_id;
  }, [
    addConversation,
    createSession,
    handleActiveConversationChange,
    processingRunId,
  ]);


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
        const filter = action.slots?.filter ?? "awaiting_review";
        window.location.href = `/evidence?review_status=${filter ?? "awaiting_review"}`;
        return;
      }

      if (action.intent === "start-pipeline" || action.intent === "upload-pdf") {
        setActiveForm(action.intent);
        setActiveFormSlots(action.slots ?? {});
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

  // ── Poll pipeline status ──
  const pollPipelineStatus = useCallback(async (runId: string) => {
    const TERMINAL = new Set([
      "completed",
      "failed",
      "awaiting_review",
      "cancelled",
    ]);
    const MAX_POLL_MS = 30 * 60 * 1000; // 30 min safety cap
    const startedAt = Date.now();
    let consecutiveErrors = 0;

    const poll = async () => {
      try {
        const { data } = await apiClient.get<{
          pipeline_status: string;
          phases: Record<
            string,
            { status: string; duration_seconds?: number | null }
          >;
        }>(`/pipeline/runs/${runId}/status`);
        consecutiveErrors = 0;
        setPipelineStatus({
          runId,
          status: data.pipeline_status,
          phases: data.phases,
        });
        if (
          !TERMINAL.has(data.pipeline_status) &&
          Date.now() - startedAt < MAX_POLL_MS
        ) {
          setTimeout(poll, 2000);
        }
      } catch {
        consecutiveErrors++;
        if (consecutiveErrors < 10 && Date.now() - startedAt < MAX_POLL_MS) {
          setTimeout(poll, 2000);
        }
      }
    };
    setTimeout(poll, 1000);
  }, [setPipelineStatus]);

  // ── Pipeline form submit ──
  const handlePipelineSubmit = useCallback(
    async (data: PipelineFormData) => {
      setActiveForm(null);
      try {
        const body: Record<string, unknown> = {
          source_type: data.sourceType,
          mode: "full",
        };
        if (data.sourceType === "online" && data.query) {
          body.query = data.query;
        } else if (data.sourceType === "local" && data.file) {
          body.content_base64 = await readFileAsBase64(data.file);
          body.filename = data.file.name;
        }
        const response = await apiClient.post<{
          processing_run_id: string;
          status: string;
        }>("/pipeline/run", body);
        const runId = response.data.processing_run_id;
        setPipelineStatus({ runId, status: response.data.status });
        // Only post to chat if a session is active; otherwise the
        // pipeline status card alone is sufficient feedback.
        if (activeProvider) {
          onRequest?.({
            messages: [
              {
                role: "assistant" as const,
                content: `Pipeline started. Run ID: ${runId.slice(0, 8)}...`,
              },
            ],
          });
        }
        pollPipelineStatus(runId);
      } catch (err: unknown) {
        console.error("[Pipeline] start failed:", err);
        antdMessage.error(
          `Failed to start pipeline: ${extractErrorMessage(err)}`,
        );
      }
    },
    [
      activeProvider,
      onRequest,
      pollPipelineStatus,
      setActiveForm,
      setPipelineStatus,
    ],
  );

  // ── Build bubble items with contentRender for embedded forms ──
  const bubbleItems = useMemo(() => {
    const messageKeys = toUniqueChatMessageKeys(messages);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const items: any[] = messages.map(({ id, message, status }, index) => {
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

    if (activeForm === "start-pipeline" || activeForm === "upload-pdf") {
      items.push({
        key: "__form__",
        role: "assistant",
        content: "",
        variant: "borderless" as const,
        contentRender: () => (
          <PipelineStartForm
            key={`${activeForm}:${activeFormSlots?.query ?? ""}`}
            defaultSourceType={activeForm === "upload-pdf" ? "local" : "online"}
            defaultQuery={
              activeForm === "start-pipeline"
                ? activeFormSlots?.query ?? undefined
                : undefined
            }
            onSubmit={handlePipelineSubmit}
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
          <WelcomeBlock onPick={(msg) => void handleSendMessage(msg)} />
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
    handlePipelineSubmit,
    handleSendMessage,
    dispatchedActions,
    handleDispatchAction,
  ]);

  // ── Create session ──
  async function handleCreateSession() {
    try {
      await createAndActivateSession();
    } catch {
      antdMessage.error("Failed to create session");
    }
  }

  // ── Delete session (client-side hide; backend has no DELETE endpoint) ──
  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      Modal.confirm({
        title: "Delete this chat session?",
        content:
          "The session is removed from the sidebar. The conversation itself is still reachable via direct URL.",
        okText: "Delete",
        okButtonProps: { danger: true },
        cancelText: "Cancel",
        onOk: () => {
          clearCachedMessageStore(sessionId);
          removeSession(sessionId);
          removeConversation(sessionId);
          // Evict per-session UI state so it doesn't accumulate (#9).
          setSessionUI((prev) => {
            const next = { ...prev };
            delete next[sessionId];
            return next;
          });
          if (activeConversationKey === sessionId) {
            const remaining = sessions.filter((s) => s.session_id !== sessionId);
            const next = remaining[0]?.session_id;
            if (next) {
              handleActiveConversationChange(next);
            } else {
              setActiveConversationKey("");
            }
          }
        },
      });
    },
    [
      activeConversationKey,
      handleActiveConversationChange,
      removeConversation,
      removeSession,
      sessions,
      setActiveConversationKey,
    ],
  );

  // Conversations menu factory: a single "Delete" entry per session.
  const conversationsMenu = useCallback(
    (item: { key: string }) => ({
      items: [
        {
          key: "delete",
          label: "Delete",
          icon: <DeleteOutlined />,
          danger: true,
          onClick: ({
            domEvent,
          }: {
            domEvent: React.MouseEvent | React.KeyboardEvent;
          }) => {
            domEvent.stopPropagation();
            handleDeleteSession(item.key);
          },
        },
      ],
    }),
    [handleDeleteSession],
  );

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
      <div className="flex h-full overflow-hidden bg-white">
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
        <div className="flex min-w-0 flex-1 flex-col">
          <Bubble.List
            className="flex-1 overflow-auto"
            style={{ padding: 16 }}
            items={bubbleItems}
            role={roles}
            autoScroll
          />

          <Sender
            ref={senderRef}
            className="border-t border-gray-100"
            style={{ padding: 16 }}
            loading={isRequesting}
            onCancel={() => {
              try {
                abort?.();
              } catch {
                // See effect comment above.
              }
            }}
            onSubmit={handleSubmitAndClear}
            placeholder="Ask the Cross Evidence Agent..."
          />
        </div>
      </div>
    </XProvider>
  );
}

// ─── Single Session Chat ───────────────────────────────────────────────

function SingleSessionChat({ sessionId }: { sessionId: string }) {
  const provider = useMemo(
    () => createAcmgChatProvider(sessionId),
    [sessionId],
  );

  const { messages, onRequest, isRequesting, abort } = useXChat({
    provider,
    conversationKey: sessionId,
    defaultMessages: async () =>
      toXChatDefaultMessages(await listMessages(sessionId)),
  });

  const bubbleItems = useMemo(() => {
    const messageKeys = toUniqueChatMessageKeys(messages);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const items: any[] = messages.map(({ message, status }, index) => {
      const isLoadingEmpty =
        (status === "loading" || status === "updating") && !message.content;
      const isStreaming =
        !isLoadingEmpty &&
        (status === "loading" || status === "updating") &&
        Boolean(message.content);

      return {
        key: messageKeys[index],
        role: message.role,
        content: message.content,
        streaming: false,
        loading: false,
        ...(message.role === "assistant"
          ? {
              contentRender: (content: string) => {
                if (isLoadingEmpty) {
                  return <ThinkingIndicator />;
                }
                return (
                  <div className={isStreaming ? "chat-streaming-cursor" : ""}>
                    <ChatMarkdown source={content} />
                  </div>
                );
              },
            }
          : {}),
      };
    });

    if (items.length === 0) {
      items.unshift({
        key: "__welcome__",
        role: "assistant",
        content: "",
        streaming: false,
        loading: false,
        variant: "borderless",
        contentRender: () => <WelcomeBlock />,
      });
    }

    return items;
  }, [messages]);

  const senderRef = useRef<SenderRef>(null);
  const handleSingleSessionSubmit = useCallback(
    (val: string) => {
      const trimmed = val.trim();
      if (!trimmed) return;
      const task = (async () => {
        try {
          await sendChatMessage(sessionId, trimmed);
          onRequest({ messages: [{ role: "user", content: trimmed }] });
        } catch {
          antdMessage.error("Failed to send message");
        }
      })();
      void task.finally(() => senderRef.current?.clear());
    },
    [onRequest, sessionId],
  );

  return (
    <XProvider>
      <div className="flex h-full flex-col overflow-hidden bg-white">
        <Bubble.List
          className="flex-1 overflow-auto"
          style={{ padding: 16 }}
          items={bubbleItems}
          role={roles}
          autoScroll
        />

        <Sender
          ref={senderRef}
          className="border-t border-gray-100"
          style={{ padding: 16 }}
          loading={isRequesting}
          onCancel={() => {
            try {
              abort?.();
            } catch {
              // See FullChatView effect comment.
            }
          }}
          onSubmit={handleSingleSessionSubmit}
          placeholder="Ask the Cross Evidence Agent..."
        />
      </div>
    </XProvider>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(",")[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
