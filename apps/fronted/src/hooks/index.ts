/**
 * Hooks 统一导出
 */
export { useChapters, type Chapter } from './useChapters';
export { useIntersectionObserver } from './useIntersectionObserver';
export { useScrollSync, type ScrollState } from './useScrollSync';
export { 
  useTaskPolling, 
  useMultiTaskPolling, 
  useTaskQueue,
  type UseTaskPollingOptions,
  type UseTaskPollingReturn,
  type TaskQueueItem,
} from './useTaskPolling';
export {
  useTaskWebSocket,
  useWebSocketTaskPolling,
  type UseWebSocketOptions,
  type UseWebSocketReturn,
} from './useWebSocket';
