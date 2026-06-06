"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { streamUrl } from "../services/chat";

interface UseChatStreamOptions {
  sessionId: string;
  onToken?: (token: string) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
  enabled?: boolean;
}

/**
 * SSE streaming hook for real-time AI chat replies.
 *
 * Connects to GET /chat/sessions/{id}/stream and emits events
 * via callbacks. Callbacks are stored in refs so the connect
 * callback identity is stable across renders — prevents the
 * infinite reconnect loop that would occur if connect depended
 * on freshly-created callback references.
 */
export function useChatStream({
  sessionId,
  onToken,
  onDone,
  onError,
  enabled = true,
}: UseChatStreamOptions) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Store callbacks in refs so connect doesn't re-create on every render.
  const onTokenRef = useRef(onToken);
  onTokenRef.current = onToken;
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    disconnect();

    const url = streamUrl(sessionId);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => setIsConnected(true);

    es.addEventListener("token", (e) => {
      onTokenRef.current?.(e.data);
    });

    es.addEventListener("done", () => {
      onDoneRef.current?.();
      disconnect();
    });

    es.addEventListener("error", (e) => {
      const eventData = (e as MessageEvent).data;
      onErrorRef.current?.(eventData ?? "Stream error");
      disconnect();
    });

    es.onerror = () => {
      setIsConnected(false);
      disconnect();
    };
  }, [sessionId, disconnect]);

  useEffect(() => {
    if (enabled && sessionId) {
      connect();
    }
    return disconnect;
  }, [enabled, sessionId, connect, disconnect]);

  return { isConnected, connect, disconnect };
}
