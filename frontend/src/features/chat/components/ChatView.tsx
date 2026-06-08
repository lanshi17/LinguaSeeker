"use client";

import { useCallback, useMemo, useState } from "react";
import {
  XProvider,
  Bubble,
  Sender,
  Conversations,
  Welcome,
  Prompts,
} from "@ant-design/x";
import { useXChat, useXConversations } from "@ant-design/x-sdk";
import { RobotOutlined, UserOutlined } from "@ant-design/icons";
import { Avatar, message as antdMessage } from "antd";
import { createAcmgChatProvider, sendChatMessage } from "../providers/acmgChatProvider";
import { useChatSessions } from "../hooks/useChatSessions";
import {
  PipelineStartForm,
  PipelineStatusCard,
} from "./forms";
import type { PipelineFormData } from "./forms";
import { apiClient } from "@/lib/api/client";
import { extractErrorMessage } from "@/lib/api/error";

interface ChatViewProps {
  processingRunId?: string;
  sessionId?: string;
}

// ─── Role config for Bubble.List ───────────────────────────────────────

const roles = {
  assistant: {
    placement: "start" as const,
    avatar: (
      <Avatar
        icon={<RobotOutlined />}
        style={{ backgroundColor: "#0891b2" }}
      />
    ),
  },
  user: {
    placement: "end" as const,
    avatar: (
      <Avatar
        icon={<UserOutlined />}
        style={{ backgroundColor: "#22c55e" }}
      />
    ),
  },
};

// ─── Prompt suggestions ────────────────────────────────────────────────

const PROMPT_ITEMS = [
  {
    key: "start-pipeline",
    label: "Start Pipeline",
    description: "Analyze a biomedical paper and extract ACMG evidence.",
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

  const { sessions, createSession, isCreating } = useChatSessions(
    processingRunId ?? "",
  );

  const conversationItems = useMemo(
    () =>
      sessions.map((s) => ({
        key: s.session_id,
        label: `Session ${s.session_id.slice(0, 8)}`,
      })),
    [sessions],
  );

  const {
    conversations,
    activeConversationKey,
    setActiveConversationKey,
    addConversation,
  } = useXConversations({
    defaultConversations: conversationItems,
    defaultActiveConversationKey: sessions[0]?.session_id,
  });

  const activeProvider = activeConversationKey
    ? getProvider(activeConversationKey)
    : undefined;

  const { messages, onRequest, isRequesting, abort } = useXChat({
    provider: activeProvider,
    conversationKey: activeConversationKey,
    // Parse backend's JSON SSE format: {"type":"text","content":"..."} → "..."
    parser: (msg) => {
      if (msg.role !== "assistant" || !msg.content) return msg;
      try {
        const parsed = JSON.parse(msg.content);
        if (parsed.type === "text" && parsed.content) {
          return { ...msg, content: parsed.content };
        }
        if (parsed.type === "error") {
          return { ...msg, content: `[Error] ${parsed.message}` };
        }
      } catch {
        // Not JSON — use as-is
      }
      return msg;
    },
  });

  // ── Embedded form state (declared before callbacks that use it) ──
  const [activeForm, setActiveForm] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<{
    runId: string;
    status: string;
    phases?: Record<string, { status: string; duration_seconds?: number | null }>;
  } | null>(null);

  // ── Send message: POST to persist, then stream AI reply ──
  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!activeConversationKey) return;
      setActiveForm(null);
      try {
        await sendChatMessage(activeConversationKey, content);
        onRequest({ messages: [{ role: "user", content }] });
      } catch {
        antdMessage.error("Failed to send message");
      }
    },
    [activeConversationKey, onRequest, setActiveForm],
  );

  // ── Poll pipeline status ──
  const pollPipelineStatus = useCallback(async (runId: string) => {
    const TERMINAL = new Set(["completed", "failed", "awaiting_review", "cancelled"]);
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
        if (!TERMINAL.has(data.pipeline_status) && Date.now() - startedAt < MAX_POLL_MS) {
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
        antdMessage.error(`Failed to start pipeline: ${extractErrorMessage(err)}`);
      }
    },
    [activeProvider, onRequest, pollPipelineStatus, setActiveForm, setPipelineStatus],
  );

  // ── Build bubble items with contentRender for embedded forms ──
  const bubbleItems = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const items: any[] = messages.map(({ id, message, status }) => ({
      key: id,
      role: message.role,
      content: message.content,
      streaming: status === "loading" || status === "updating",
      loading: status === "loading" && !message.content,
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
  }, [messages, activeForm, pipelineStatus, isRequesting, handlePipelineSubmit]);

  // ── Prompt click handler ──
  function handlePromptClick(key: string) {
    if (key === "start-pipeline" || key === "upload-pdf") {
      // Show embedded form instead of sending a text message
      setActiveForm(key);
      const content =
        key === "start-pipeline"
          ? "I want to start an evidence extraction pipeline."
          : "I want to upload a PDF for evidence extraction.";
      handleSendMessage(content);
      return;
    }

    if (key === "search-evidence") {
      window.location.href = "/evidence";
      return;
    }

    const prompt = PROMPT_ITEMS.find((p) => p.key === key);
    if (prompt) {
      handleSendMessage(prompt.description);
    }
  }

  // ── Create session ──
  async function handleCreateSession() {
    if (!processingRunId) {
      antdMessage.warning("Start a pipeline first to create a chat session.");
      return;
    }
    try {
      const session = await createSession();
      addConversation({
        key: session.session_id,
        label: `Session ${session.session_id.slice(0, 8)}`,
      });
      setActiveConversationKey(session.session_id);
    } catch {
      antdMessage.error("Failed to create session");
    }
  }

  return (
    <XProvider>
      <div
        className="flex rounded-lg border border-gray-200 bg-white"
        style={{ height: "calc(100vh - 12rem)" }}
      >
        {/* Conversation sidebar */}
        <Conversations
          style={{ width: 240, borderRight: "1px solid #f0f0f0" }}
          items={conversations}
          activeKey={activeConversationKey}
          onActiveChange={setActiveConversationKey}
          creation={{
            onClick: handleCreateSession,
            disabled: isCreating,
          }}
        />

        {/* Main chat area */}
        <div className="flex flex-1 flex-col">
          {bubbleItems.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center">
              <Welcome
                title="ACMG Lingua Agent"
                description="I'll guide you through evidence extraction. Upload a paper, search by PMID, or ask me anything about variant classification."
                variant="borderless"
              />
              <Prompts
                items={PROMPT_ITEMS}
                wrap
                onItemClick={(info) =>
                  handlePromptClick(info.data.key as string)
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
            className="border-t border-gray-100"
            style={{ padding: 16 }}
            loading={isRequesting}
            onCancel={abort}
            onSubmit={handleSendMessage}
            placeholder="Ask the ACMG Agent..."
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
  });

  const bubbleItems = useMemo(
    () =>
      messages.map(({ id, message, status }) => ({
        key: id,
        role: message.role,
        content: message.content,
        streaming: status === "loading" || status === "updating",
        loading: status === "loading" && !message.content,
      })),
    [messages],
  );

  return (
    <XProvider>
      <div
        className="flex flex-col rounded-lg border border-gray-200 bg-white"
        style={{ height: "calc(100vh - 12rem)" }}
      >
        {bubbleItems.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center">
            <Welcome
              title="ACMG Lingua Agent"
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
          className="border-t border-gray-100"
          style={{ padding: 16 }}
          loading={isRequesting}
          onCancel={abort}
          onSubmit={async (val) => {
            await sendChatMessage(sessionId, val);
            onRequest({ messages: [{ role: "user", content: val }] });
          }}
          placeholder="Ask the ACMG Agent..."
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
