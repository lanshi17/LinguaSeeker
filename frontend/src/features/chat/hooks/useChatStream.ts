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
 * via callbacks. Callbacks are stored in refs so the effect
 * doesn't re-run when the parent re-creates them.
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

  // Sync refs via effect — avoids writing during render.
  const onTokenRef = useRef(onToken);
  const onDoneRef = useRef(onDone);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onTokenRef.current = onToken;
  }, [onToken]);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  // Manage the EventSource lifecycle in a single effect.
  useEffect(() => {
    if (!enabled || !sessionId) return;

    // Close any existing connection before opening a new one.
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = streamUrl(sessionId);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => setIsConnected(true);

    es.addEventListener("token", (e) => {
      onTokenRef.current?.(e.data);
    });

    es.addEventListener("done", () => {
      onDoneRef.current?.();
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    });

    es.addEventListener("error", (e) => {
      const eventData = (e as MessageEvent).data;
      onErrorRef.current?.(eventData ?? "Stream error");
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    });

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    };
  }, [enabled, sessionId, disconnect]);

  return { isConnected, disconnect };
}
