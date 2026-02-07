/**
 * WebSocket Hook
 * 用于在 React 组件中使用 WebSocket 连接
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import type { TaskStatusResponse } from '../types';
import type { WebSocketStatus, WebSocketMessage } from '../services/websocket';
import { TaskWebSocketClient } from '../services/websocket';

export interface UseWebSocketOptions {
  enabled?: boolean;
  onMessage?: (message: WebSocketMessage) => void;
  onProgress?: (progress: number, stage?: string) => void;
  onComplete?: (data: TaskStatusResponse) => void;
  onError?: (error: Error) => void;
}

export interface UseWebSocketReturn {
  status: WebSocketStatus;
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  progress: number;
  currentStage: string | null;
  connect: () => void;
  disconnect: () => void;
  send: (message: Record<string, unknown>) => void;
}

/**
 * WebSocket Hook - 用于任务进度监控
 */
export function useTaskWebSocket(
  taskId: string | null,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [progress, setProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  
  const clientRef = useRef<TaskWebSocketClient | null>(null);

  const connect = useCallback(() => {
    if (!taskId) return;
    
    // 如果已有连接，先断开
    if (clientRef.current) {
      clientRef.current.disconnect();
    }
    
    // 创建新连接
    clientRef.current = new TaskWebSocketClient(taskId, {
      onStatusChange: setStatus,
      onMessage: (message) => {
        setLastMessage(message);
        options.onMessage?.(message);
      },
      onProgress: (prog, stage) => {
        setProgress(prog);
        if (stage) setCurrentStage(stage);
        options.onProgress?.(prog, stage);
      },
      onComplete: (data) => {
        setProgress(100);
        options.onComplete?.(data);
      },
      onError: options.onError,
      reconnectAttempts: 5,
      reconnectDelay: 2000,
    });
    
    clientRef.current.connect();
  }, [taskId, options]);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
    clientRef.current = null;
  }, []);

  const send = useCallback((message: Record<string, unknown>) => {
    clientRef.current?.send(message);
  }, []);

  // 自动连接
  useEffect(() => {
    if (options.enabled !== false && taskId) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [taskId, options.enabled, connect, disconnect]);

  return {
    status,
    isConnected: status === 'connected',
    lastMessage,
    progress,
    currentStage,
    connect,
    disconnect,
    send,
  };
}

/**
 * 替代轮询的 WebSocket 任务监控 Hook
 */
export function useWebSocketTaskPolling(
  taskId: string | null,
  onComplete?: (data: TaskStatusResponse) => void,
  onError?: (error: Error) => void
): {
  isWatching: boolean;
  progress: number;
  currentStage: string | null;
  status: WebSocketStatus;
  startWatching: () => void;
  stopWatching: () => void;
} {
  const [isWatching, setIsWatching] = useState(false);
  
  const ws = useTaskWebSocket(taskId, {
    enabled: isWatching,
    onProgress: (prog) => {
      console.log(`[WebSocket] 任务进度: ${prog}%`);
    },
    onComplete: (data) => {
      setIsWatching(false);
      onComplete?.(data);
    },
    onError: (error) => {
      setIsWatching(false);
      onError?.(error);
    },
  });

  const startWatching = useCallback(() => {
    setIsWatching(true);
  }, []);

  const stopWatching = useCallback(() => {
    setIsWatching(false);
  }, []);

  return {
    isWatching,
    progress: ws.progress,
    currentStage: ws.currentStage,
    status: ws.status,
    startWatching,
    stopWatching,
  };
}

export default useTaskWebSocket;
