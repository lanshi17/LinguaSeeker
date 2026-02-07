/**
 * 任务轮询 Hook
 * 用于实时获取任务状态和进度
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import type { TaskStatusResponse, TaskStatusValue } from '../types';
import { getTaskStatus, createTaskPoller, APIError } from '../services/api';

export interface UseTaskPollingOptions {
  /** 轮询间隔 (毫秒) */
  interval?: number;
  /** 最大轮询次数 */
  maxAttempts?: number;
  /** 是否在完成时自动停止 */
  stopOnComplete?: boolean;
}

export interface UseTaskPollingReturn {
  /** 当前任务状态 */
  status: TaskStatusResponse | null;
  /** 是否正在轮询 */
  isPolling: boolean;
  /** 是否出错 */
  error: Error | null;
  /** 开始轮询 */
  startPolling: (taskId: string) => void;
  /** 停止轮询 */
  stopPolling: () => void;
  /** 刷新状态 */
  refresh: () => Promise<void>;
}

/**
 * 任务轮询 Hook
 * 用于实时监控任务处理进度
 */
export function useTaskPolling(
  onProgress?: (status: TaskStatusResponse) => void,
  onComplete?: (status: TaskStatusResponse) => void,
  onError?: (error: Error) => void,
  options: UseTaskPollingOptions = {}
): UseTaskPollingReturn {
  const {
    interval = 2000,
    stopOnComplete = true,
  } = options;

  const [status, setStatus] = useState<TaskStatusResponse | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  const taskIdRef = useRef<string | null>(null);
  const pollerRef = useRef<ReturnType<typeof createTaskPoller> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  /**
   * 停止轮询
   */
  const stopPolling = useCallback(() => {
    if (pollerRef.current) {
      pollerRef.current.abort();
      pollerRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  /**
   * 清理函数
   */
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  /**
   * 开始轮询
   */
  const startPolling = useCallback((taskId: string) => {
    // 停止现有轮询
    stopPolling();
    
    taskIdRef.current = taskId;
    setError(null);
    setIsPolling(true);
    
    // 创建新的 poller
    const poller = createTaskPoller();
    pollerRef.current = poller;
    
    // 开始轮询
    poller.poll(
      taskId,
      (newStatus) => {
        setStatus(newStatus);
        onProgress?.(newStatus);
        
        // 检查是否完成
        if (stopOnComplete && 
            (newStatus.status === 'completed' || 
             newStatus.status === 'failed' || 
             newStatus.status === 'cancelled')) {
          stopPolling();
          onComplete?.(newStatus);
        }
      },
      interval
    ).catch((err) => {
      if (err instanceof APIError && err.message === '轮询已取消') {
        return;
      }
      setError(err as Error);
      onError?.(err as Error);
      setIsPolling(false);
    });
  }, [interval, stopOnComplete, onProgress, onComplete, onError, stopPolling]);

  /**
   * 手动刷新状态
   */
  const refresh = useCallback(async () => {
    if (!taskIdRef.current) {
      throw new Error('没有正在轮询的任务');
    }
    
    try {
      const newStatus = await getTaskStatus(taskIdRef.current);
      setStatus(newStatus);
      onProgress?.(newStatus);
    } catch (err) {
      setError(err as Error);
      throw err;
    }
  }, [onProgress]);

  return {
    status,
    isPolling,
    error,
    startPolling,
    stopPolling,
    refresh,
  };
}

/**
 * 多个任务轮询 Hook
 * 用于同时监控多个任务
 */
export function useMultiTaskPolling(
  onTaskProgress?: (taskId: string, status: TaskStatusResponse) => void,
  onTaskComplete?: (taskId: string, status: TaskStatusResponse) => void,
  options: UseTaskPollingOptions = {}
) {
  const [tasks, setTasks] = useState<Map<string, TaskStatusResponse>>(new Map());
  const pollersRef = useRef<Map<string, ReturnType<typeof createTaskPoller>>>(new Map());

  const interval = options.interval ?? 2000;

  /**
   * 添加任务到轮询
   */
  const addTask = useCallback((taskId: string) => {
    if (pollersRef.current.has(taskId)) {
      return; // 已经在轮询中
    }

    const poller = createTaskPoller();
    pollersRef.current.set(taskId, poller);

    poller.poll(
      taskId,
      (status) => {
        setTasks(prev => new Map(prev).set(taskId, status));
        onTaskProgress?.(taskId, status);

        if (status.status === 'completed' || 
            status.status === 'failed' || 
            status.status === 'cancelled') {
          removeTask(taskId);
          onTaskComplete?.(taskId, status);
        }
      },
      interval
    ).catch(() => {
      // 忽略取消错误
    });
  }, [interval, onTaskProgress, onTaskComplete]);

  /**
   * 移除任务轮询
   */
  const removeTask = useCallback((taskId: string) => {
    const poller = pollersRef.current.get(taskId);
    if (poller) {
      poller.abort();
      pollersRef.current.delete(taskId);
    }
  }, []);

  /**
   * 停止所有轮询
   */
  const stopAll = useCallback(() => {
    pollersRef.current.forEach(poller => poller.abort());
    pollersRef.current.clear();
    setTasks(new Map());
  }, []);

  // 清理
  useEffect(() => {
    return () => {
      stopAll();
    };
  }, [stopAll]);

  return {
    tasks,
    addTask,
    removeTask,
    stopAll,
  };
}

/**
 * 任务队列 Hook
 * 管理多个任务的提交和监控
 */
export interface TaskQueueItem {
  id: string;
  type: 'pdf_upload' | 'pmid_fetch' | 'doi_fetch';
  title: string;
  description?: string;
  status: TaskStatusValue;
  progress: number;
  currentStage?: string;
  documentId?: string;
  error?: string;
  createdAt: string;
}

export function useTaskQueue() {
  const [queue, setQueue] = useState<TaskQueueItem[]>([]);

  /**
   * 添加任务到队列
   */
  const addTask = useCallback((task: Omit<TaskQueueItem, 'status' | 'progress' | 'createdAt'>) => {
    const newTask: TaskQueueItem = {
      ...task,
      status: 'pending',
      progress: 0,
      createdAt: new Date().toISOString(),
    };
    setQueue(prev => [newTask, ...prev]);
    return newTask.id;
  }, []);

  /**
   * 更新任务状态
   */
  const updateTask = useCallback((taskId: string, updates: Partial<TaskQueueItem>) => {
    setQueue(prev => prev.map(task => 
      task.id === taskId ? { ...task, ...updates } : task
    ));
  }, []);

  /**
   * 更新任务进度
   */
  const updateTaskProgress = useCallback((taskId: string, status: TaskStatusResponse) => {
    setQueue(prev => prev.map(task => {
      if (task.id !== taskId) return task;
      return {
        ...task,
        status: status.status,
        progress: status.progress_percentage,
        currentStage: status.current_stage || undefined,
        documentId: status.document_id,
        error: status.error_message || undefined,
      };
    }));
  }, []);

  /**
   * 移除任务
   */
  const removeTask = useCallback((taskId: string) => {
    setQueue(prev => prev.filter(task => task.id !== taskId));
  }, []);

  /**
   * 清空已完成任务
   */
  const clearCompleted = useCallback(() => {
    setQueue(prev => prev.filter(task => 
      task.status !== 'completed' && task.status !== 'failed' && task.status !== 'cancelled'
    ));
  }, []);

  /**
   * 获取活跃任务数量
   */
  const activeCount = queue.filter(t => t.status === 'pending' || t.status === 'processing').length;
  const completedCount = queue.filter(t => t.status === 'completed').length;

  return {
    queue,
    activeCount,
    completedCount,
    addTask,
    updateTask,
    updateTaskProgress,
    removeTask,
    clearCompleted,
  };
}

export default useTaskPolling;
