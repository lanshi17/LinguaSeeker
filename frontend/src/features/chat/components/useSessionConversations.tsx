import { useCallback, useEffect, useMemo, useState } from "react";
import type { MutableRefObject } from "react";
import { useXConversations } from "@ant-design/x-sdk";
import { Trash2 } from "lucide-react";
import { Modal, message as antdMessage } from "antd";
import { useChatSessions } from "../hooks/useChatSessions";
import {
  loadActiveChatSession,
  rememberActiveChatSession,
  upsertLocalChatSession,
} from "../utils/localSessions";
import { clearCachedMessageStore } from "../utils/messageStore";
import { SESSION_TITLE_WORDS } from "./chatConfig";

/**
 * Manages chat sessions, conversation sidebar, session CRUD, and
 * the useXConversations binding. Wraps useChatSessions (backend API)
 * with client-side label overrides and sidebar menu logic.
 *
 * `onSessionDeletedRef` is a mutable ref (not a direct callback) so
 * the caller can wire up a callback that depends on state not yet
 * available when this hook is first called.
 */
export function useSessionConversations(
  processingRunId: string | undefined,
  onSessionDeletedRef?: MutableRefObject<(id: string) => void>,
) {
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

  // ── Create session ──
  const handleCreateSession = useCallback(async () => {
    try {
      await createAndActivateSession();
    } catch {
      antdMessage.error("Failed to create session");
    }
  }, [createAndActivateSession]);

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
          onSessionDeletedRef?.current(sessionId);
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
      onSessionDeletedRef,
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
          icon: <Trash2 style={{ width: 14, height: 14 }} />,
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

  return {
    sessions,
    isCreating,
    conversations,
    activeConversationKey,
    setActiveConversationKey,
    handleActiveConversationChange,
    createAndActivateSession,
    captureFirstMessageLabel,
    handleCreateSession,
    handleDeleteSession,
    conversationsMenu,
  };
}
