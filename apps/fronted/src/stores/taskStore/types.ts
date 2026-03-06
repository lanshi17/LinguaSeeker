import type { 
  TaskListItem, 
  TaskStatusResponse, 
  TaskRequestStatusResponse,
  PubMedCandidateItem,
  PubMedCandidateSearchRequest
} from '../../types/api';

export interface TaskFilters {
  status?: string;
  searchQuery?: string;
  dateFilter?: string;
}

export interface PollingConfig {
  tasksListInterval: number;      // milliseconds
  taskDetailInterval: number;     // milliseconds
  requestInterval: number;        // milliseconds
  maxPollingAttempts: number;
}

export interface TaskSliceState {
  tasks: TaskListItem[];
  tasksLoading: boolean;
  tasksError: string | null;
  lastTasksUpdate: Date | null;
  
  selectedTask: TaskStatusResponse | null;
  selectedTaskLoading: boolean;
  selectedTaskError: string | null;
  
  currentRequest: TaskRequestStatusResponse | null;
  requestLoading: boolean;
  requestError: string | null;
  
  candidates: PubMedCandidateItem[];
  candidatesLoading: boolean;
  candidatesError: string | null;
  
  pollingIntervals: Map<string, ReturnType<typeof setInterval>>;
  pollingConfig: PollingConfig;
}

export interface TaskSliceActions {
  fetchTasks: (filters?: TaskFilters) => Promise<void>;
  fetchTask: (taskId: string) => Promise<void>;
  fetchRequest: (requestId: string) => Promise<void>;
  fetchCandidates: (request: PubMedCandidateSearchRequest) => Promise<void>;
  
  startTaskPolling: (taskId: string) => void;
  stopTaskPolling: (taskId: string) => void;
  startRequestPolling: (requestId: string) => void;
  stopRequestPolling: (requestId: string) => void;
  startTasksListPolling: () => void;
  stopTasksListPolling: () => void;
  
  clearSelectedTask: () => void;
  clearRequest: () => void;
  reset: () => void;
}

export type TaskSlice = TaskSliceState & TaskSliceActions;