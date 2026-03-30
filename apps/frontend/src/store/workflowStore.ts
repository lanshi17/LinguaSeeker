import { create } from 'zustand';

import { useToastStore } from './useToastStore';

import type { TaskRequestStatusResponse, TaskStatusResponse } from '../types/api';
import type { WorkflowTimelineStep } from '../types/stream';

type WorkflowService = {
  connectToRequest: (requestId: string) => void;
  connectToTask: (taskId: string) => void;
  disconnectAll: () => void;
  subscribe: (channel: string, listener: (payload: unknown) => void) => () => void;
};

type WorkflowState = {
  currentRequest: TaskRequestStatusResponse | null;
  currentTask: TaskStatusResponse | null;
  requestTimeline: WorkflowTimelineStep[];
  taskTimeline: WorkflowTimelineStep[];
  requestConnection: { requestId: string | null; connected: boolean };
  taskConnection: { taskId: string | null; connected: boolean };
  watchRequest: (requestId: string) => void;
  watchTask: (taskId: string) => void;
  reset: () => void;
};

const baseTimeline = (): WorkflowTimelineStep[] => ([
  { id: 'queued', label: 'Queued', status: 'pending' },
  { id: 'running', label: 'Running', status: 'pending' },
  { id: 'success', label: 'Completed', status: 'pending' },
]);

function toCompleted(index: number, timeline: WorkflowTimelineStep[]) {
  return timeline.map((step, currentIndex) => {
    if (currentIndex < index) {
      return { ...step, status: 'completed' as const };
    }
    return step;
  });
}

export function projectRequestToTimelineSteps(request: TaskRequestStatusResponse): WorkflowTimelineStep[] {
  const timeline = baseTimeline();
  timeline[0] = { ...timeline[0], status: 'completed' };

  if (request.status === 'success') {
    return toCompleted(3, timeline).map((step) => ({ ...step, status: 'completed' }));
  }

  return [
    { ...timeline[0], status: 'completed' },
    { ...timeline[1], status: 'running' },
    timeline[2],
  ];
}

export function projectTaskToTimelineSteps(task: TaskStatusResponse): WorkflowTimelineStep[] {
  const timeline = baseTimeline();
  const runningStep: WorkflowTimelineStep = {
    ...timeline[1],
    status: task.status === 'failure' ? 'error' : 'running',
    description: task.workflow_status_description ?? undefined,
    progress: task.progress_percentage ?? undefined,
  };

  if (task.status === 'success') {
    return [
      { ...timeline[0], status: 'completed' },
      { ...timeline[1], status: 'completed', description: task.workflow_status_description ?? undefined, progress: task.progress_percentage ?? undefined },
      { ...timeline[2], status: 'completed' },
    ];
  }

  return [
    { ...timeline[0], status: 'completed' },
    runningStep,
    timeline[2],
  ];
}

export function createWorkflowStore(service: WorkflowService) {
  let unsubscribeRequest: (() => void) | null = null;
  let unsubscribeTask: (() => void) | null = null;

  return create<WorkflowState>((set) => ({
    currentRequest: null,
    currentTask: null,
    requestTimeline: baseTimeline(),
    taskTimeline: baseTimeline(),
    requestConnection: { requestId: null, connected: false },
    taskConnection: { taskId: null, connected: false },
    watchRequest: (requestId) => {
      unsubscribeRequest?.();
      unsubscribeRequest = service.subscribe(`request:${requestId}`, (payload) => {
        const request = payload as TaskRequestStatusResponse;
        set({
          currentRequest: request,
          requestTimeline: projectRequestToTimelineSteps(request),
          requestConnection: { requestId, connected: true },
        });
      });
      service.connectToRequest(requestId);
    },
    watchTask: (taskId) => {
      unsubscribeTask?.();
      unsubscribeTask = service.subscribe(`task:${taskId}`, (payload) => {
        const task = payload as TaskStatusResponse;
        set({
          currentTask: task,
          taskTimeline: projectTaskToTimelineSteps(task),
          taskConnection: { taskId, connected: true },
        });
        if (task.error || task.status === 'failure') {
          useToastStore.getState().pushToast({
            level: 'error',
            title: 'Task stream error',
            message: task.error ?? 'Task stream reported a failure',
            ttlMs: 5000,
          });
        }
      });
      service.connectToTask(taskId);
    },
    reset: () => {
      unsubscribeRequest?.();
      unsubscribeTask?.();
      unsubscribeRequest = null;
      unsubscribeTask = null;
      service.disconnectAll();
      set({
        currentRequest: null,
        currentTask: null,
        requestTimeline: baseTimeline(),
        taskTimeline: baseTimeline(),
        requestConnection: { requestId: null, connected: false },
        taskConnection: { taskId: null, connected: false },
      });
    },
  }));
}
