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
import { createAcmgChatProvider } from "../providers/acmgChatProvider";
import { useChatSessions } from "../hooks/useChatSessions";

interface ChatViewProps {
  processingRunId?: string;
  sessionId?: string;
}

/** Role config for Bubble.List — defined outside render. */
const roles = {
  assistant: {
    placement: "start" as const,
    avatar: (
      <Avatar
        icon={<RobotOutlined />}
        style={{ backgroundColor: "#1677ff" }}
      />
    ),
  },
  user: {
    placement: "end" as const,
    avatar: (
      <Avatar
        icon={<UserOutlined />}
        style={{ backgroundColor: "#87d068" }}
      />
    ),
  },
};

/** ACMG Agent prompt suggestions. */
const PROMPT_ITEMS = [
  {
    key: "classify",
    label: "ACMG Classification",
    description: "Help classify a genetic variant using ACMG criteria",
  },
  {
    key: "evidence",
    label: "Evidence Review",
    description: "Review and discuss extracted evidence",
  },
  {
    key: "explain",
    label: "Explain Result",
    description: "Explain a pipeline result in plain language",
  },
];

/**
 * Full-featured AI chat view using @ant-design/x.
 *
 * Supports:
 * - Conversation sidebar with create/delete
 * - Streaming AI responses with typing animation
 * - Welcome screen with prompt suggestions
 * - Abort/cancel in-flight requests
 */
export function ChatView({ processingRunId, sessionId }: ChatViewProps) {
  // If a specific session is provided, show single-session chat.
  if (sessionId) {
    return <SingleSessionChat sessionId={sessionId} />;
  }

  // If a processing run is provided, show full chat with conversation sidebar.
  if (processingRunId) {
    return <FullChatView processingRunId={processingRunId} />;
  }

  // No context — show standalone chat.
  return <FullChatView />;
}

// ─── Full Chat View (with conversation sidebar) ───────────────────────

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

  const {
    sessions,
    createSession,
    isCreating,
  } = useChatSessions(processingRunId ?? "");

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

  const { messages, onRequest, isRequesting, abort } = useXChat({
    provider: getProvider(activeConversationKey ?? ""),
    conversationKey: activeConversationKey,
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
                description="Ask questions about variant classification, evidence review, or pipeline results."
                variant="borderless"
              />
              <Prompts
                items={PROMPT_ITEMS}
                wrap
                onItemClick={(info) => {
                  onRequest({
                    messages: [
                      {
                        role: "user",
                        content: info.data.description as string,
                      },
                    ],
                  });
                }}
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
            onSubmit={(val) =>
              onRequest({
                messages: [{ role: "user", content: val }],
              })
            }
            placeholder="Ask the ACMG Agent..."
          />
        </div>
      </div>
    </XProvider>
  );
}

// ─── Single Session Chat (no sidebar) ─────────────────────────────────

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
          onSubmit={(val) =>
            onRequest({
              messages: [{ role: "user", content: val }],
            })
          }
          placeholder="Ask the ACMG Agent..."
        />
      </div>
    </XProvider>
  );
}
