
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
import { PipelineSummaryCard, PipelineStatusCard } from "./forms";
import type { PipelineSummarySlots } from "./forms";
import { ChatActionBubble } from "./ChatActionBubble";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { apiClient } from "@/lib/api/client";
import { extractErrorMessage } from "@/lib/api/error";
import {
  BookOpen,
  FlaskConical,
  ListChecks,
  Search,
  Sparkles,
  Upload,
} from "lucide-react";
import { TaskQueuePanel } from "@/features/pipeline";

/** Max words of the first user message used as the session title. */
const SESSION_TITLE_WORDS = 5;

/** localStorage key for the task-queue panel visibility preference. */
const TASK_QUEUE_STORAGE_KEY = "chat.taskQueueOpen";

function readInitialQueueOpen(): boolean {
  if (typeof window === "undefined") return true;
  const stored = window.localStorage.getItem(TASK_QUEUE_STORAGE_KEY);
  return stored === null ? true : stored === "1";
}

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
  accentBg: string;
  accentColor: string;
}

const SUGGESTIONS: SuggestionChip[] = [
  {
    icon: <FlaskConical style={{ width: 16, height: 16 }} />,
    title: "Run the pipeline",
    description: "Ingest a paper via PMID, DOI, or keyword",
    message: "Run the four-phase pipeline on PMID 34521984",
    accentBg: "#ecfeff",
    accentColor: "#0891b2",
  },
  {
    icon: <Upload style={{ width: 16, height: 16 }} />,
    title: "Upload a PDF",
    description: "Parse, translate, and extract evidence",
    message: "I want to upload a PDF",
    accentBg: "#f5f3ff",
    accentColor: "#7c3aed",
  },
  {
    icon: <Search style={{ width: 16, height: 16 }} />,
    title: "Search evidence",
    description: "Query extracted evidence by gene or variant",
    message: "Search the evidence database",
    accentBg: "#ecfdf5",
    accentColor: "#059669",
  },
  {
    icon: <BookOpen style={{ width: 16, height: 16 }} />,
    title: "Classify a variant",
    description: "Walk through ACMG/AMP 2015 criteria",
    message: "Help me classify a variant with ACMG criteria",
    accentBg: "#fffbeb",
    accentColor: "#d97706",
  },
];

interface WelcomeBlockProps {
  onPick?: (message: string) => void;
}

function WelcomeBlock({ onPick }: WelcomeBlockProps) {
  return (
    <>
      <style>{`
        @media (min-width: 640px) {
          .cv-suggestions-grid { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
        }
        .cv-suggestion-chip {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          border-radius: 12px;
          border: 1px solid #f3f4f6;
          background-color: #fff;
          padding: 12px;
          text-align: left;
          transition: all 150ms;
          cursor: pointer;
        }
        .cv-suggestion-chip:hover {
          transform: translateY(-2px);
          border-color: #e5e7eb;
          box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05);
        }
        .cv-suggestion-chip:disabled {
          cursor: default;
          transform: none;
          border-color: #f3f4f6;
          box-shadow: none;
        }
      `}</style>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div
            style={{
              display: "flex",
              height: 36,
              width: 36,
              flex: "none",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 12,
              background: "linear-gradient(to bottom right, #06b6d4, #2563eb)",
              color: "#fff",
              boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            }}
          >
            <Sparkles style={{ width: 16, height: 16 }} aria-hidden="true" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.025em", color: "#111827" }}>
              Welcome to <span style={{ color: "#0891b2" }}>Lingua Seeker</span>
            </h2>
            <p style={{ fontSize: 13.5, lineHeight: 1.625, color: "#4b5563" }}>
              A literature-grounded assistant for variant and evidence
              classification. I run a four-phase extraction pipeline and ground
              every claim in source coordinates.
            </p>
          </div>
        </div>

        <div className="cv-suggestions-grid" style={{ display: "grid", gap: 8 }}>
          {SUGGESTIONS.map((chip) => {
            const isInteractive = Boolean(onPick);
            return (
              <button
                key={chip.title}
                type="button"
                onClick={() => onPick?.(chip.message)}
                disabled={!isInteractive}
                className="cv-suggestion-chip"
              >
                <span
                  style={{
                    display: "flex",
                    height: 32,
                    width: 32,
                    flex: "none",
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 8,
                    backgroundColor: chip.accentBg,
                    color: chip.accentColor,
                  }}
                >
                  {chip.icon}
                </span>
                <span style={{ minWidth: 0, flex: 1 }}>
                  <span
                    style={{
                      display: "block",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "#111827",
                    }}
                  >
                    {chip.title}
                  </span>
                  <span
                    style={{
                      marginTop: 2,
                      display: "block",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      fontSize: 12,
                      color: "#6b7280",
                    }}
                  >
                    {chip.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <p
          style={{
            borderTop: "1px solid #f3f4f6",
            paddingTop: 12,
            fontSize: 11.5,
            lineHeight: 1.625,
            color: "#9ca3af",
          }}
        >
          The agent does not provide clinical diagnoses. Outputs are research-grade
          evidence for review by qualified professionals.
        </p>
      </div>
    </>
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

  const [taskQueueOpen, setTaskQueueOpen] = useState<boolean>(
    readInitialQueueOpen,
  );
  const toggleTaskQueue = useCallback(() => {
    setTaskQueueOpen((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(
          TASK_QUEUE_STORAGE_KEY,
          next ? "1" : "0",
        );
      } catch {
        // Storage quota or sandboxed env — silently ignore.
      }
      return next;
    });
  }, []);

  const [providerCache] = useState(
    () => new Map<string, ReturnType<typeof createAcmgChatProvider>>(),
  );

  // Track the previous session's provider so we can abort its stream
  // reliably during session switches — useXChat's abort reference can
  // already point to the new provider by the time the switch effect runs.
  const prevProviderRef = useRef<ReturnType<typeof createAcmgChatProvider> | null>(
    null,
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

    // Abort the *previous* session's provider directly.  We track the
    // previous provider in a ref because `useXChat` re-binds to the new
    // provider during the render that triggers this effect — by the time
    // the effect body runs, any abort closure from `useXChat` already
    // points at the *new* provider and cannot cancel the old stream.
    const prevProvider = prevProviderRef.current;
    if (prevProvider) {
      try {
        prevProvider.abort();
      } catch {
        // Swallow — abort is idempotent; if it throws the stream was
        // already gone or the provider is in a terminal state.
      }
    }

    if (!activeConversationKey) {
      setMessages?.([]);
      prevProviderRef.current = null;
      return;
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

    // Remember the current provider as the "previous" for the next switch.
    prevProviderRef.current = activeProvider ?? null;

    return () => {
      cancelled = true;
    };
    // activeProvider is derived from activeConversationKey + a stable cache
    // and is included so prevProviderRef is updated correctly when the
    // provider reference changes (e.g. after cache miss → create).
  }, [activeConversationKey, activeProvider, setMessages]);

  // Abort any in-flight stream when the FullChatView unmounts entirely
  // (e.g. user navigates away from the chat page).
  useEffect(() => {
    return () => {
      const current = prevProviderRef.current;
      if (current) {
        try {
          current.abort();
        } catch {
          // No-op on unmount — best-effort cleanup.
        }
      }
    };
  }, []);

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

  // ── Poll pipeline status ──
  const pollPipelineStatus = useCallback(async (runId: string) => {
    const TERMINAL = new Set([
      "completed",
      "failed",
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

  // ── Pipeline confirm: submit from the conversational summary card ──
  const handlePipelineConfirm = useCallback(
    async (slots: PipelineSummarySlots) => {
      setActiveForm(null);
      try {
        const body: Record<string, unknown> = {
          source_type: slots.source_type ?? "online",
          mode: "full",
        };
        if (slots.source_type !== "local") {
          if (slots.query) body.query = slots.query;
          if (slots.identifiers) {
            body.identifiers = slots.identifiers
              .split(/[,\s]+/)
              .map((s) => s.trim())
              .filter(Boolean);
          }
        }
        if (
          slots.gene_symbol ||
          slots.disease_name ||
          slots.variant_hgvs_p
        ) {
          body.target = {
            gene_symbol: slots.gene_symbol || undefined,
            disease_name: slots.disease_name || undefined,
            variant_hgvs_p: slots.variant_hgvs_p || undefined,
          };
        }
        const response = await apiClient.post<{
          processing_run_id: string;
          status: string;
        }>("/pipeline/run", body);
        const runId = response.data.processing_run_id;
        setPipelineStatus({ runId, status: response.data.status });
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
    handlePipelineConfirm,
    handleSendMessage,
    dispatchedActions,
    handleDispatchAction,
    setActiveForm,
    setActiveFormSlots,
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
          outline: 2px solid #0891b2;
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

// ─── Single Session Chat ───────────────────────────────────────────────

function SingleSessionChat({ sessionId }: { sessionId: string }) {
  const provider = useMemo(
    () => createAcmgChatProvider(sessionId),
    [sessionId],
  );

  const xChat = useXChat({
    provider,
    conversationKey: sessionId,
    defaultMessages: async () => [], // Start empty, load in useEffect
  });

  // Guard against undefined returns from useXChat
  const messages = xChat?.messages ?? [];
  const onRequest = xChat?.onRequest;
  const isRequesting = xChat?.isRequesting ?? false;
  const abort = xChat?.abort;
  const setMessages = xChat?.setMessages;

  // Explicit message hydration on mount (same pattern as FullChatView).
  // Also aborts any in-flight stream when sessionId changes or on unmount.
  // `provider` is stable (memoized on sessionId) so the cleanup closure
  // captures the correct instance for each session.
  useEffect(() => {
    let cancelled = false;

    setMessages?.([]);

    listMessages(sessionId)
      .then((history) => {
        if (cancelled) return;
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
      // Abort the SSE stream when the single-session view unmounts
      // (e.g. user navigates away, or sessionId changes).
      try {
        provider.abort();
      } catch {
        // No-op on unmount — best-effort cleanup.
      }
    };
  }, [sessionId, setMessages, provider]);

  const handleQuickAction = useCallback(
    (message: string) => {
      const task = (async () => {
        try {
          await sendChatMessage(sessionId, message);
          // Use onRequest to properly manage useXChat state
          if (onRequest) {
            onRequest({ messages: [{ role: "user" as const, content: message }] });
          }
        } catch {
          antdMessage.error("Failed to send message");
        }
      })();
      void task;
    },
    [onRequest, sessionId],
  );

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
        contentRender: () => <WelcomeBlock onPick={handleQuickAction} />,
      });
    }

    return items;
  }, [messages, handleQuickAction]);

  const senderRef = useRef<SenderRef>(null);
  const handleSingleSessionSubmit = useCallback(
    (val: string) => {
      const trimmed = val.trim();
      if (!trimmed) return;
      const task = (async () => {
        try {
          await sendChatMessage(sessionId, trimmed);
          if (onRequest) {
            onRequest({ messages: [{ role: "user" as const, content: trimmed }] });
          } else {
            console.warn("[ChatView] onRequest is undefined - message sent but not displayed");
          }
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
      <div style={{ display: "flex", height: "100%", flexDirection: "column", overflow: "hidden", backgroundColor: "#fff" }}>
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
            // reliable fetch termination. Also try the SDK's abort
            // as a secondary cleanup for internal state.
            try {
              provider.abort();
            } catch {
                // noop
            }
            try {
              abort?.();
            } catch {
                // noop
            }
          }}
          onSubmit={handleSingleSessionSubmit}
          placeholder="Ask the Lingua Seeker Agent..."
        />
      </div>
    </XProvider>
  );
}
