"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  XProvider,
  Bubble,
  Sender,
  Conversations,
  Welcome,
  Prompts,
} from "@ant-design/x";
import type { SenderRef } from "@ant-design/x/es/sender/interface";
import { useXChat, useXConversations } from "@ant-design/x-sdk";
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
} from "../utils/messageHistory";
import { detectChatActionIntent } from "../utils/intent";
import { ChatMarkdown } from "../utils/markdown";
import { PipelineStartForm, PipelineStatusCard } from "./forms";
import type { PipelineFormData } from "./forms";
import { apiClient } from "@/lib/api/client";
import { extractErrorMessage } from "@/lib/api/error";

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

// ─── Prompt suggestions ────────────────────────────────────────────────

const PROMPT_ITEMS = [
  {
    key: "start-pipeline",
    label: "Start Pipeline",
    description: "Analyze a biomedical paper and extract evidence.",
  },
  {
    key: "upload-pdf",
    label: "Upload PDF",
    description: "Upload a PDF document for evidence extraction.",
  },
  {
    key: "search-evidence",
    label: "Search Evidence",
    description: "Search existing evidence by gene, variant, or disease.",
  },
];

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

  const loadDefaultMessages = useCallback(
    async (info?: { conversationKey?: string }) => {
      if (!info?.conversationKey) return [];
      const history = await listMessages(info.conversationKey);
      return toXChatDefaultMessages(history);
    },
    [],
  );

  const {
    messages,
    onRequest,
    isRequesting,
    abort,
    queueRequest,
    setMessages,
  } = useXChat({
    provider: activeProvider,
    conversationKey: activeConversationKey,
    defaultMessages: loadDefaultMessages,
  });

  // ── Embedded form state (declared before callbacks that use it) ──
  const [activeForm, setActiveForm] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<{
    runId: string;
    status: string;
    phases?: Record<
      string,
      { status: string; duration_seconds?: number | null }
    >;
  } | null>(null);

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

  const ensureActiveSession = useCallback(async (): Promise<string> => {
    if (activeConversationKey) return activeConversationKey;
    return createAndActivateSession();
  }, [activeConversationKey, createAndActivateSession]);

  const appendLocalUserMessage = useCallback(
    (content: string) => {
      setMessages((current) => [
        ...current,
        {
          id: `local_${Date.now()}_${current.length}`,
          message: { role: "user" as const, content },
          status: "local" as const,
        },
      ]);
    },
    [setMessages],
  );

  // ── Send message: create session if needed, POST to persist, then stream AI reply ──
  const handleSendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;

      setActiveForm(null);

      const actionIntent = detectChatActionIntent(trimmed);
      if (actionIntent === "search-evidence") {
        window.location.href = "/evidence";
        return;
      }

      if (actionIntent === "start-pipeline" || actionIntent === "upload-pdf") {
        try {
          const sessionKey = await ensureActiveSession();
          await sendChatMessage(sessionKey, trimmed);
          captureFirstMessageLabel(sessionKey, trimmed);

          if (sessionKey === activeConversationKey) {
            appendLocalUserMessage(trimmed);
          }

          setActiveForm(actionIntent);
        } catch {
          antdMessage.error("Failed to open evidence extraction form");
        }
        return;
      }

      try {
        const sessionKey = await ensureActiveSession();
        await sendChatMessage(sessionKey, trimmed);
        captureFirstMessageLabel(sessionKey, trimmed);
        const request = {
          messages: [{ role: "user" as const, content: trimmed }],
        };

        if (sessionKey === activeConversationKey) {
          onRequest(request);
          return;
        }

        queueRequest(sessionKey, request);
      } catch {
        antdMessage.error("Failed to send message");
      }
    },
    [
      activeConversationKey,
      appendLocalUserMessage,
      captureFirstMessageLabel,
      ensureActiveSession,
      onRequest,
      queueRequest,
      setActiveForm,
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
  }, []);

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
          onRequest({
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
    const items: any[] = messages.map(({ message, status }, index) => ({
      key: messageKeys[index],
      role: message.role,
      content: message.content,
      streaming: status === "loading" || status === "updating",
      loading: status === "loading" && !message.content,
      // Render assistant replies as Markdown; user messages are typically
      // plain text and pass through verbatim.
      ...(message.role === "assistant"
        ? {
            contentRender: (content: string) => (
              <ChatMarkdown source={content} />
            ),
          }
        : {}),
    }));

    // Append form bubble if active
    if (activeForm === "start-pipeline" || activeForm === "upload-pdf") {
      items.push({
        key: "__form__",
        role: "assistant",
        content: "",
        variant: "borderless" as const,
        contentRender: () => (
          <PipelineStartForm
            key={activeForm}
            defaultSourceType={activeForm === "upload-pdf" ? "local" : "online"}
            onSubmit={handlePipelineSubmit}
            isSubmitting={isRequesting}
          />
        ),
      });
    }

    // Append status bubble if pipeline is running
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

    return items;
  }, [
    messages,
    activeForm,
    pipelineStatus,
    isRequesting,
    handlePipelineSubmit,
  ]);

  // ── Prompt click handler ──
  async function handlePromptClick(key: string) {
    if (key === "start-pipeline" || key === "upload-pdf") {
      try {
        await ensureActiveSession();
        setActiveForm(key);
      } catch {
        antdMessage.error("Failed to create session");
      }
      return;
    }

    if (key === "search-evidence") {
      window.location.href = "/evidence";
      return;
    }

    const prompt = PROMPT_ITEMS.find((p) => p.key === key);
    if (prompt) {
      void handleSendMessage(prompt.description);
    }
  }

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
          removeSession(sessionId);
          removeConversation(sessionId);
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
      <div className="flex min-h-[620px] overflow-hidden rounded-md border border-gray-200 bg-white shadow-sm md:h-[calc(100vh-8.5rem)]">
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
          {bubbleItems.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-8 text-center md:px-10">
              <Welcome
                title="Cross EvidenceAgent"
                description="I'll guide you through evidence extraction. Upload a paper, search by PMID, or ask me anything about variant classification."
                variant="borderless"
              />
              <Prompts
                className="w-full max-w-3xl"
                items={PROMPT_ITEMS}
                wrap
                onItemClick={(info) =>
                  void handlePromptClick(info.data.key as string)
                }
              />
            </div>
          ) : (
            <Bubble.List
              className="flex-1 overflow-auto"
              style={{ padding: 16 }}
              items={bubbleItems}
              role={roles}
              autoScroll
            />
          )}

          <Sender
            ref={senderRef}
            className="border-t border-gray-100"
            style={{ padding: 16 }}
            loading={isRequesting}
            onCancel={abort}
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
    return messages.map(({ message, status }, index) => ({
      key: messageKeys[index],
      role: message.role,
      content: message.content,
      streaming: status === "loading" || status === "updating",
      loading: status === "loading" && !message.content,
      ...(message.role === "assistant"
        ? {
            contentRender: (content: string) => (
              <ChatMarkdown source={content} />
            ),
          }
        : {}),
    }));
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
      <div className="flex min-h-[620px] flex-col overflow-hidden rounded-md border border-gray-200 bg-white shadow-sm md:h-[calc(100vh-8.5rem)]">
        {bubbleItems.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-8 text-center md:px-10">
            <Welcome
              title="Cross EvidenceAgent"
              description="Ask questions about variant classification, evidence review, or pipeline results."
              variant="borderless"
            />
          </div>
        ) : (
          <Bubble.List
            className="flex-1 overflow-auto"
            style={{ padding: 16 }}
            items={bubbleItems}
            role={roles}
            autoScroll
          />
        )}

        <Sender
          ref={senderRef}
          className="border-t border-gray-100"
          style={{ padding: 16 }}
          loading={isRequesting}
          onCancel={abort}
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
