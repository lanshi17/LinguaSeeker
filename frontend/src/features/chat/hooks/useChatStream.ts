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
 * via callbacks. Reconnects on transient failures with backoff.
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
      onToken?.(e.data);
    });

    es.addEventListener("done", () => {
      onDone?.();
      disconnect();
    });

    es.addEventListener("error", (e) => {
      const eventData = (e as MessageEvent).data;
      onError?.(eventData ?? "Stream error");
      disconnect();
    });

    es.onerror = () => {
      setIsConnected(false);
      // EventSource auto-reconnects by default; close on persistent error.
      disconnect();
    };
  }, [sessionId, onToken, onDone, onError, disconnect]);

  useEffect(() => {
    if (enabled && sessionId) {
      connect();
    }
    return disconnect;
  }, [enabled, sessionId, connect, disconnect]);

  return { isConnected, connect, disconnect };
}
