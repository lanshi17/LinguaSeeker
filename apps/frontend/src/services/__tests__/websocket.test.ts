import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createWebSocketService } from '../websocket';

type MockWebSocket = {
  onopen: ((this: WebSocket, ev: Event) => unknown) | null;
  onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null;
  onerror: ((this: WebSocket, ev: Event) => unknown) | null;
  onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null;
  readyState: number;
  close: () => void;
  send: (data: string) => void;
};

describe('createWebSocketService', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('connects to the expected request stream URL and forwards parsed JSON messages', () => {
    const createdSockets: { url: string; socket: MockWebSocket }[] = [];

    const WebSocketImpl = vi.fn(class {
      onopen: ((this: WebSocket, ev: Event) => unknown) | null = null;
      onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null = null;
      onerror: ((this: WebSocket, ev: Event) => unknown) | null = null;
      onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null = null;
      readyState = 0;
      close = vi.fn();
      send = vi.fn();

      constructor(url: string) {
        createdSockets.push({ url, socket: this as unknown as MockWebSocket });
      }
    });

    const service = createWebSocketService({
      wsUrl: 'ws://localhost:8000',
      WebSocketImpl: WebSocketImpl as unknown as typeof WebSocket,
    });

    const onMessage = vi.fn();
    const unsubscribe = service.subscribe('request:req-123', onMessage);

    service.connectToRequest('req-123');
    expect(WebSocketImpl).toHaveBeenCalledTimes(1);
    expect(createdSockets[0]?.url).toBe('ws://localhost:8000/api/v1/stream/requests/req-123');

    createdSockets[0]?.socket.onmessage?.call(
      createdSockets[0].socket as unknown as WebSocket,
      {
        data: JSON.stringify({ request_id: 'req-123', status: 'running', papers: [] }),
      } as MessageEvent
    );

    expect(onMessage).toHaveBeenCalledWith({ request_id: 'req-123', status: 'running', papers: [] });

    unsubscribe();
    service.disconnectAll();
  });

  it('allows unsubscribing without affecting other listeners', () => {
    const WebSocketImpl = vi.fn(class {
      onopen: ((this: WebSocket, ev: Event) => unknown) | null = null;
      onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null = null;
      onerror: ((this: WebSocket, ev: Event) => unknown) | null = null;
      onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null = null;
      readyState = 0;
      close = vi.fn();
      send = vi.fn();
    });

    const service = createWebSocketService({
      wsUrl: 'ws://localhost:8000',
      WebSocketImpl: WebSocketImpl as unknown as typeof WebSocket,
    });

    const listenerA = vi.fn();
    const listenerB = vi.fn();

    const unsubA = service.subscribe('task:task-1', listenerA);
    service.subscribe('task:task-1', listenerB);

    unsubA();

    service.connectToTask('task-1');
    expect(WebSocketImpl).toHaveBeenCalledTimes(1);

    service.disconnectAll();
  });
});
