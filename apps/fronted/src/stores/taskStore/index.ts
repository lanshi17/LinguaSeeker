import type { StateCreator } from 'zustand';
import type { TaskSlice, TaskFilters } from './types';
import { 
  getTasks, 
  getTaskStatus, 
  getTaskRequestStatus, 
  searchPubMedCandidates 
} from '../../services/api';

export type { TaskSlice } from './types';

const DEFAULT_POLLING_CONFIG = {
  tasksListInterval: 5000,
  taskDetailInterval: 2000,
  requestInterval: 3000,
  maxPollingAttempts: 300,
};

export const createTaskSlice: StateCreator<TaskSlice> = (set, get) => ({
  tasks: [],
  tasksLoading: false,
  tasksError: null,
  lastTasksUpdate: null,
  
  selectedTask: null,
  selectedTaskLoading: false,
  selectedTaskError: null,
  
  currentRequest: null,
  requestLoading: false,
  requestError: null,
  
  candidates: [],
  candidatesLoading: false,
  candidatesError: null,
  
  pollingIntervals: new Map(),
  pollingConfig: DEFAULT_POLLING_CONFIG,
  
  fetchTasks: async (filters?: TaskFilters) => {
    set({ tasksLoading: true, tasksError: null });
    try {
      const response = await getTasks();
      let filteredTasks = response.items || [];
      
      if (filters?.status && filters.status !== 'all') {
        filteredTasks = filteredTasks.filter(t => t.status === filters.status);
      }
      if (filters?.searchQuery) {
        const query = filters.searchQuery.toLowerCase();
        filteredTasks = filteredTasks.filter(t => 
          t.task_id.toLowerCase().includes(query) ||
          t.status.toLowerCase().includes(query)
        );
      }
      
      set({ 
        tasks: filteredTasks, 
        tasksLoading: false, 
        lastTasksUpdate: new Date() 
      });
    } catch (error: any) {
      set({ 
        tasksError: error?.detail || 'Failed to fetch tasks', 
        tasksLoading: false 
      });
    }
  },
  
  fetchTask: async (taskId: string) => {
    set({ selectedTaskLoading: true, selectedTaskError: null });
    try {
      const task = await getTaskStatus(taskId);
      set({ 
        selectedTask: task, 
        selectedTaskLoading: false 
      });
    } catch (error: any) {
      set({ 
        selectedTaskError: error?.detail || 'Failed to fetch task', 
        selectedTaskLoading: false 
      });
    }
  },
  
  fetchRequest: async (requestId: string) => {
    set({ requestLoading: true, requestError: null });
    try {
      const request = await getTaskRequestStatus(requestId);
      set({ 
        currentRequest: request, 
        requestLoading: false 
      });
    } catch (error: any) {
      set({ 
        requestError: error?.detail || 'Failed to fetch request', 
        requestLoading: false 
      });
    }
  },
  
  fetchCandidates: async (request: any) => {
    set({ candidatesLoading: true, candidatesError: null });
    try {
      const response = await searchPubMedCandidates(request);
      set({ 
        candidates: response.candidates || [], 
        candidatesLoading: false 
      });
    } catch (error: any) {
      set({ 
        candidatesError: error?.detail || 'Failed to fetch candidates', 
        candidatesLoading: false 
      });
    }
  },
  
  startTaskPolling: (taskId: string) => {
    const { pollingIntervals, pollingConfig } = get();
    
    if (pollingIntervals.has(`task-${taskId}`)) {
      return;
    }
    
    const intervalId = setInterval(async () => {
      await get().fetchTask(taskId);
      
      const task = get().selectedTask;
      const terminalStatuses = ['SUCCESS', 'FAILURE', 'REVOKED'];
      
      if (task && terminalStatuses.includes(task.status)) {
        get().stopTaskPolling(taskId);
      }
    }, pollingConfig.taskDetailInterval);
    
    set({
      pollingIntervals: new Map(pollingIntervals).set(`task-${taskId}`, intervalId)
    });
  },
  
  stopTaskPolling: (taskId: string) => {
    const { pollingIntervals } = get();
    const intervalId = pollingIntervals.get(`task-${taskId}`);
    
    if (intervalId) {
      clearInterval(intervalId);
      const newMap = new Map(pollingIntervals);
      newMap.delete(`task-${taskId}`);
      set({ pollingIntervals: newMap });
    }
  },
  
  startRequestPolling: (requestId: string) => {
    const { pollingIntervals, pollingConfig } = get();
    
    if (pollingIntervals.has(`request-${requestId}`)) {
      return;
    }
    
    const intervalId = setInterval(async () => {
      await get().fetchRequest(requestId);
      
      const request = get().currentRequest;
      const terminalStatuses = ['success', 'failed', 'partial_failed'];
      
      if (request && terminalStatuses.includes(request.status)) {
        get().stopRequestPolling(requestId);
      }
    }, pollingConfig.requestInterval);
    
    set({
      pollingIntervals: new Map(pollingIntervals).set(`request-${requestId}`, intervalId)
    });
  },
  
  stopRequestPolling: (requestId: string) => {
    const { pollingIntervals } = get();
    const intervalId = pollingIntervals.get(`request-${requestId}`);
    
    if (intervalId) {
      clearInterval(intervalId);
      const newMap = new Map(pollingIntervals);
      newMap.delete(`request-${requestId}`);
      set({ pollingIntervals: newMap });
    }
  },
  
  startTasksListPolling: () => {
    const { pollingIntervals, pollingConfig } = get();
    
    if (pollingIntervals.has('tasksList')) {
      return;
    }
    
    const intervalId = setInterval(() => {
      get().fetchTasks();
    }, pollingConfig.tasksListInterval);
    
    set({
      pollingIntervals: new Map(pollingIntervals).set('tasksList', intervalId)
    });
  },
  
  stopTasksListPolling: () => {
    const { pollingIntervals } = get();
    const intervalId = pollingIntervals.get('tasksList');
    
    if (intervalId) {
      clearInterval(intervalId);
      const newMap = new Map(pollingIntervals);
      newMap.delete('tasksList');
      set({ pollingIntervals: newMap });
    }
  },
  
  clearSelectedTask: () => {
    set({ 
      selectedTask: null, 
      selectedTaskError: null 
    });
  },
  
  clearRequest: () => {
    set({ 
      currentRequest: null, 
      requestError: null 
    });
  },
  
  reset: () => {
    const { pollingIntervals } = get();
    pollingIntervals.forEach((interval) => clearInterval(interval));
    
    set({
      tasks: [],
      tasksLoading: false,
      tasksError: null,
      lastTasksUpdate: null,
      selectedTask: null,
      selectedTaskLoading: false,
      selectedTaskError: null,
      currentRequest: null,
      requestLoading: false,
      requestError: null,
      candidates: [],
      candidatesLoading: false,
      candidatesError: null,
      pollingIntervals: new Map(),
    });
  },
}));