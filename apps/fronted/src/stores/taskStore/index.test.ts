import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../services/api', () => ({
  getTasks: vi.fn(() => Promise.resolve({ items: [] })),
  getTaskStatus: vi.fn(() => Promise.resolve({ task_id: 'test-id', status: 'PENDING' })),
  getTaskRequestStatus: vi.fn(() => Promise.resolve({ request_id: 'test-request-id', status: 'pending' })),
  searchPubMedCandidates: vi.fn(() => Promise.resolve({ candidates: [] })),
}));

describe('TaskStore', () => {
  beforeEach(async () => {
    const { useAppStore } = await import('../index');
    useAppStore.getState().reset();
  });

  describe('fetchTasks', () => {
    it('should fetch tasks and update state', async () => {
      const { useAppStore } = await import('../index');
      const store = useAppStore.getState();
      
      await store.fetchTasks();
      
      expect(store.tasks).toEqual([]);
      expect(store.tasksLoading).toBe(false);
      expect(store.tasksError).toBe(null);
    });

    it('should filter tasks by status', async () => {
      const { useAppStore } = await import('../index');
      const store = useAppStore.getState();
      
      await store.fetchTasks({ status: 'SUCCESS' });
      
      expect(store.tasks).toEqual([]);
    });

    it('should filter tasks by search query', async () => {
      const { useAppStore } = await import('../index');
      const store = useAppStore.getState();
      
      await store.fetchTasks({ searchQuery: 'test' });
      
      expect(store.tasks).toEqual([]);
    });
  });

  describe('fetchTask', () => {
    it('should fetch single task and update state', async () => {
      const { useAppStore } = await import('../index');
      const store = useAppStore.getState();
      
      await store.fetchTask('test-task-id');
      
      expect(store.selectedTask).not.toBe(null);
      expect(store.selectedTaskLoading).toBe(false);
    });
  });

  describe('fetchRequest', () => {
    it('should fetch request and update state', async () => {
      const { useAppStore } = await import('../index');
      const store = useAppStore.getState();
      
      await store.fetchRequest('test-request-id');
      
      expect(store.currentRequest).not.toBe(null);
      expect(store.requestLoading).toBe(false);
    });
  });

  describe('clearSelectedTask', () => {
    it('should clear selected task', async () => {
      const { useAppStore } = await import('../index');
      const store = useAppStore.getState();
      
      await store.fetchTask('test-task-id');
      expect(store.selectedTask).not.toBe(null);
      
      store.clearSelectedTask();
      expect(store.selectedTask).toBe(null);
    });
  });

  describe('clearRequest', () => {
    it('should clear current request', async () => {
      const { useAppStore } = await import('../index');
      const store = useAppStore.getState();
      
      await store.fetchRequest('test-request-id');
      expect(store.currentRequest).not.toBe(null);
      
      store.clearRequest();
      expect(store.currentRequest).toBe(null);
    });
  });

  describe('reset', () => {
    it('should reset all state to initial values', async () => {
      const { useAppStore } = await import('../index');
      const store = useAppStore.getState();
      
      await store.fetchTasks();
      await store.fetchTask('test-task-id');
      
      store.reset();
      
      expect(store.tasks).toEqual([]);
      expect(store.selectedTask).toBe(null);
      expect(store.currentRequest).toBe(null);
      expect(store.pollingIntervals.size).toBe(0);
    });
  });
});