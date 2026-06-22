import { useCallback, useEffect, useRef, useState } from "react";
import { useXChat } from "@ant-design/x-sdk";
import type { MessageInfo } from "@ant-design/x-sdk/es/x-chat";
import { createAcmgChatProvider } from "../providers/acmgChatProvider";
import { listMessages } from "../services/chat";
import {
  toXChatDefaultMessages,
  type ChatBubbleMessage,
} from "../utils/messageHistory";

/**
 * Manages the chat provider lifecycle: caching per-session providers,
 * binding useXChat, hydrating messages on session switch, and aborting
 * in-flight streams on switch/unmount.
 */
export function useChatProvider(activeConversationKey: string | undefined) {
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

  // Abort any in-flight stream when the component using this hook unmounts
  // entirely (e.g. user navigates away from the chat page).
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

  return { activeProvider, messages, onRequest, isRequesting, abort, setMessages };
}
