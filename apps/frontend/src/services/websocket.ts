import { getApiBaseUrl } from '../config/env';

type Listener = (payload: unknown) => void;

type WebSocketServiceOptions = {
  wsUrl?: string;
  WebSocketImpl?: typeof WebSocket;
};

function normalizeWsBaseUrl(baseUrl: string) {
  if (baseUrl.startsWith('ws://') || baseUrl.startsWith('wss://')) {
    return baseUrl.replace(/\/$/, '');
  }

  const trimmed = baseUrl.replace(/\/$/, '');
  const isHttps = typeof window !== 'undefined' && window.location.protocol === 'https:';
  const scheme = isHttps ? 'wss' : 'ws';
  return `${scheme}://${trimmed.replace(/^https?:\/\//, '')}`;
}

function defaultWsBaseUrl() {
  const apiBase = getApiBaseUrl();
  if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
    return normalizeWsBaseUrl(apiBase);
  }

  if (typeof window === 'undefined') {
    return 'ws://localhost:8000';
  }

  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${window.location.host}`;
}

export function createWebSocketService(options: WebSocketServiceOptions = {}) {
  const WebSocketCtor = options.WebSocketImpl ?? WebSocket;
  const wsBaseUrl = normalizeWsBaseUrl(options.wsUrl ?? defaultWsBaseUrl());

  const sockets = new Map<string, WebSocket>();
  const listeners = new Map<string, Set<Listener>>();

  function subscribe(channel: string, listener: Listener) {
    const set = listeners.get(channel) ?? new Set();
    set.add(listener);
    listeners.set(channel, set);

    return () => {
      const existing = listeners.get(channel);
      if (!existing) return;
      existing.delete(listener);
      if (existing.size === 0) {
        listeners.delete(channel);
      }
    };
  }

  function notify(channel: string, payload: unknown) {
    const set = listeners.get(channel);
    if (!set) return;
    set.forEach((listener) => {
      listener(payload);
    });
  }

  function ensureSocket(key: string, url: string, channel: string) {
    const existing = sockets.get(key);
    if (existing && existing.readyState !== WebSocket.CLOSED) {
      return existing;
    }

    const socket = new WebSocketCtor(url);
    socket.onmessage = (ev) => {
      try {
        const payload = JSON.parse(String(ev.data));
        notify(channel, payload);
      } catch {
        notify(channel, { error: 'invalid_json', raw: ev.data });
      }
    };
    socket.onerror = () => {
      notify(channel, { error: 'socket_error' });
    };
    socket.onclose = () => {
      sockets.delete(key);
    };

    sockets.set(key, socket);
    return socket;
  }

  function connectToRequest(requestId: string) {
    const key = `request:${requestId}`;
    const url = `${wsBaseUrl}/api/v1/stream/requests/${encodeURIComponent(requestId)}`;
    ensureSocket(key, url, `request:${requestId}`);
  }

  function connectToTask(taskId: string) {
    const key = `task:${taskId}`;
    const url = `${wsBaseUrl}/api/v1/stream/${encodeURIComponent(taskId)}`;
    ensureSocket(key, url, `task:${taskId}`);
  }

  function disconnectAll() {
    sockets.forEach((socket) => {
      try {
        socket.close();
      } catch {
        notify('system', { error: 'socket_close_failed' });
      }
    });
    sockets.clear();
  }

  return {
    subscribe,
    connectToRequest,
    connectToTask,
    disconnectAll,
  };
}

export const wsService = createWebSocketService();
