import { useCallback, useEffect, useMemo, useRef } from "react";
import { XProvider, Bubble, Sender } from "@ant-design/x";
import type { SenderRef } from "@ant-design/x/es/sender/interface";
import { useXChat } from "@ant-design/x-sdk";
import type { MessageInfo } from "@ant-design/x-sdk/es/x-chat";
import { App } from "antd";
import { extractErrorMessage } from "@/lib/api/error";
import {
  createAcmgChatProvider,
  sendChatMessage,
} from "../providers/acmgChatProvider";
import { listMessages } from "../services/chat";
import {
  toUniqueChatMessageKeys,
  toXChatDefaultMessages,
  type ChatBubbleMessage,
} from "../utils/messageHistory";
import { ChatMarkdown } from "../utils/markdown";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { WelcomeBlock } from "./WelcomeBlock";
import { roles } from "./chatConfig";

export function SingleSessionChat({ sessionId }: { sessionId: string }) {
  const { message } = App.useApp();
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
    (msg: string) => {
      const task = (async () => {
        try {
          await sendChatMessage(sessionId, msg);
          // Use onRequest to properly manage useXChat state
          if (onRequest) {
            onRequest({ messages: [{ role: "user" as const, content: msg }] });
          }
        } catch (err) {
          message.error(extractErrorMessage(err, "Failed to send message"));
        }
      })();
      void task;
    },
    [message, onRequest, sessionId],
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
      } catch (err) {
        message.error(extractErrorMessage(err, "Failed to send message"));
      }
      })();
      void task.finally(() => senderRef.current?.clear());
    },
    [message, onRequest, sessionId],
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
