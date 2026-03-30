import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createWorkflowStore, projectRequestToTimelineSteps, projectTaskToTimelineSteps } from '../workflowStore';
import { useToastStore } from '../useToastStore';

import type { TaskRequestStatusResponse, TaskStatusResponse } from '../../types/api';

describe('workflowStore', () => {
  beforeEach(() => {
    useToastStore.getState().clearToasts();
  });

  it('projects request paper states into timeline steps', () => {
    const request: TaskRequestStatusResponse = {
      request_id: 'req-1',
      status: 'running',
      papers: [
        { paper_task_id: 'paper-1', status: 'queued' },
        { paper_task_id: 'paper-2', status: 'success' },
      ],
    };

    expect(projectRequestToTimelineSteps(request)).toEqual([
      { id: 'queued', label: 'Queued', status: 'completed' },
      { id: 'running', label: 'Running', status: 'running' },
      { id: 'success', label: 'Completed', status: 'pending' },
    ]);
  });

  it('projects task status and progress into timeline steps', () => {
    const task: TaskStatusResponse = {
      task_id: 'task-1',
      status: 'started',
      workflow_status: 'parsing',
      workflow_status_description: 'Parsing PDF',
      progress_percentage: 42,
      processing_steps: {
        parsing: { status: 'running' },
      },
    };

    expect(projectTaskToTimelineSteps(task)).toEqual([
      { id: 'queued', label: 'Queued', status: 'completed' },
      { id: 'running', label: 'Running', status: 'running', description: 'Parsing PDF', progress: 42 },
      { id: 'success', label: 'Completed', status: 'pending' },
    ]);
  });

  it('stores request/task stream payloads and pushes toast on errors', () => {
    const service = {
      connectToRequest: vi.fn(),
      connectToTask: vi.fn(),
      disconnectAll: vi.fn(),
      subscribe: vi.fn((_channel: string, listener: (payload: unknown) => void) => {
        listeners.push(listener);
        return () => {};
      }),
    };
    const listeners: Array<(payload: unknown) => void> = [];

    const store = createWorkflowStore(service);

    store.getState().watchRequest('req-1');
    expect(service.connectToRequest).toHaveBeenCalledWith('req-1');

    const requestPayload: TaskRequestStatusResponse = {
      request_id: 'req-1',
      status: 'running',
      papers: [{ paper_task_id: 'paper-1', status: 'running' }],
    };
    listeners[0]?.(requestPayload);

    expect(store.getState().currentRequest).toEqual(requestPayload);
    expect(store.getState().requestTimeline).toEqual([
      { id: 'queued', label: 'Queued', status: 'completed' },
      { id: 'running', label: 'Running', status: 'running' },
      { id: 'success', label: 'Completed', status: 'pending' },
    ]);

    store.getState().watchTask('task-1');
    expect(service.connectToTask).toHaveBeenCalledWith('task-1');

    const taskPayload: TaskStatusResponse = {
      task_id: 'task-1',
      status: 'failure',
      workflow_status: 'parsing',
      error: 'Parse failed',
    };
    listeners[1]?.(taskPayload);

    expect(store.getState().currentTask).toEqual(taskPayload);
    expect(useToastStore.getState().toasts).toContainEqual(
      expect.objectContaining({ level: 'error', title: 'Task stream error' })
    );
  });
});
