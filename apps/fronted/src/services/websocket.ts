/**
 * WebSocket 服务
 * 用于实时获取任务进度更新
 * 
 * WebSocket 端点: ws://localhost:8000/ws/task/{task_id}/progress
 */

import type { TaskStatusResponse } from '../types';

export interface WebSocketMessage {
  type: 'progress' | 'status' | 'completed' | 'error' | 'connected' | 'disconnected';
  task_id: string;
  data?: TaskStatusResponse;
  progress?: number;
  stage?: string;
  message?: string;
  timestamp: string;
}

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onStatusChange?: (status: WebSocketStatus) => void;
  onProgress?: (progress: number, stage?: string) => void;
  onComplete?: (data: TaskStatusResponse) => void;
  onError?: (error: Error) => void;
  reconnectAttempts?: number;
  reconnectDelay?: number;
}

/**
 * WebSocket 任务进度客户端
 */
export class TaskWebSocketClient {
  private ws: WebSocket | null = null;
  private taskId: string;
  private options: WebSocketOptions;
  private status: WebSocketStatus = 'disconnected';
  private reconnectCount = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly maxReconnectAttempts: number;
  private readonly reconnectDelay: number;

  constructor(taskId: string, options: WebSocketOptions = {}) {
    this.taskId = taskId;
    this.options = options;
    this.maxReconnectAttempts = options.reconnectAttempts ?? 5;
    this.reconnectDelay = options.reconnectDelay ?? 3000;
  }

  /**
   * 获取 WebSocket URL
   */
  private getWebSocketUrl(): string {
    // 将 HTTP URL 转换为 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = 'localhost:8000'; // 后端 WebSocket 地址
    return `${protocol}//${host}/ws/task/${this.taskId}/progress`;
  }

  /**
   * 连接 WebSocket
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.CONNECTING || 
        this.ws?.readyState === WebSocket.OPEN) {
      console.log('[WebSocket] 已经连接或正在连接');
      return;
    }

    this.setStatus('connecting');
    
    try {
      const url = this.getWebSocketUrl();
      console.log(`[WebSocket] 连接到: ${url}`);
      
      this.ws = new WebSocket(url);
      
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
    } catch (error) {
      this.handleError(error as Event);
    }
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    this.reconnectCount = 0; // 重置重连计数，防止自动重连
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    this.setStatus('disconnected');
  }

  /**
   * 发送消息
   */
  send(message: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('[WebSocket] 连接未建立，无法发送消息');
    }
  }

  /**
   * 获取当前状态
   */
  getStatus(): WebSocketStatus {
    return this.status;
  }

  /**
   * 是否已连接
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * 处理连接打开
   */
  private handleOpen(): void {
    console.log('[WebSocket] 连接已建立');
    this.reconnectCount = 0; // 重置重连计数
    this.setStatus('connected');
    
    // 发送订阅消息
    this.send({
      action: 'subscribe',
      task_id: this.taskId,
    });
  }

  /**
   * 处理消息接收
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      console.log('[WebSocket] 收到消息:', message);
      
      this.options.onMessage?.(message);
      
      // 根据消息类型调用相应的回调
      switch (message.type) {
        case 'progress':
          if (message.progress !== undefined) {
            this.options.onProgress?.(message.progress, message.stage);
          }
          break;
        case 'completed':
          if (message.data) {
            this.options.onComplete?.(message.data);
          }
          break;
        case 'error':
          this.options.onError?.(new Error(message.message || 'WebSocket error'));
          break;
      }
    } catch (error) {
      console.error('[WebSocket] 解析消息失败:', error);
    }
  }

  /**
   * 处理连接关闭
   */
  private handleClose(event: CloseEvent): void {
    console.log(`[WebSocket] 连接关闭: code=${event.code}, reason=${event.reason}`);
    this.setStatus('disconnected');
    
    // 尝试重连
    if (this.reconnectCount < this.maxReconnectAttempts) {
      this.attemptReconnect();
    } else {
      console.log('[WebSocket] 重连次数已达上限');
      this.setStatus('error');
    }
  }

  /**
   * 处理错误
   */
  private handleError(event: Event | Error): void {
    const error = event instanceof Error ? event : new Error('WebSocket error');
    console.error('[WebSocket] 错误:', error);
    this.setStatus('error');
    this.options.onError?.(error);
  }

  /**
   * 尝试重连
   */
  private attemptReconnect(): void {
    this.reconnectCount++;
    console.log(`[WebSocket] ${this.reconnectDelay}ms 后尝试第 ${this.reconnectCount} 次重连`);
    
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, this.reconnectDelay);
  }

  /**
   * 设置状态
   */
  private setStatus(status: WebSocketStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.options.onStatusChange?.(status);
    }
  }
}

/**
 * 创建 WebSocket 客户端（简化接口）
 */
export function createTaskWebSocket(
  taskId: string,
  options: WebSocketOptions
): TaskWebSocketClient {
  return new TaskWebSocketClient(taskId, options);
}

/**
 * 使用 WebSocket 替代轮询监控任务
 */
export function watchTaskWithWebSocket(
  taskId: string,
  callbacks: {
    onProgress?: (progress: number, stage?: string) => void;
    onComplete?: (data: TaskStatusResponse) => void;
    onError?: (error: Error) => void;
    onStatusChange?: (status: WebSocketStatus) => void;
  }
): TaskWebSocketClient {
  const client = new TaskWebSocketClient(taskId, {
    onProgress: callbacks.onProgress,
    onComplete: (data) => {
      callbacks.onComplete?.(data);
      // 任务完成后自动断开连接
      setTimeout(() => client.disconnect(), 1000);
    },
    onError: callbacks.onError,
    onStatusChange: callbacks.onStatusChange,
    reconnectAttempts: 3,
    reconnectDelay: 2000,
  });
  
  client.connect();
  return client;
}

export default {
  TaskWebSocketClient,
  createTaskWebSocket,
  watchTaskWithWebSocket,
};
