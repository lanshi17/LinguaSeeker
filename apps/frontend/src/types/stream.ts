import type { TaskRequestStatusResponse, TaskStatusResponse } from './api';

export type WorkflowTimelineStatus = 'pending' | 'running' | 'completed' | 'error';

export type WorkflowTimelineStep = {
  id: 'queued' | 'running' | 'success';
  label: string;
  status: WorkflowTimelineStatus;
  description?: string;
  progress?: number;
};

export type RequestStreamPayload = TaskRequestStatusResponse;
export type TaskStreamPayload = TaskStatusResponse;

export type StreamChannel = `request:${string}` | `task:${string}`;
export type StreamPayload = RequestStreamPayload | TaskStreamPayload;

export function isTaskStreamPayload(payload: StreamPayload): payload is TaskStreamPayload {
  return 'task_id' in payload;
}

export function isRequestStreamPayload(payload: StreamPayload): payload is RequestStreamPayload {
  return 'request_id' in payload;
}
