import type { StateCreator } from 'zustand';

export interface UIFilters {
  status: string;
  searchQuery: string;
  dateFilter: string;
}

export interface UISlice {
  taskFilters: UIFilters;
  requestFilters: UIFilters;
  
  selectedTaskIds: string[];
  selectedPmids: string[];
  
  expandedTaskDetails: Set<string>;
  expandedPaperTasks: Set<string>;
  
  setTaskFilter: (key: keyof UIFilters, value: string) => void;
  setRequestFilter: (key: keyof UIFilters, value: string) => void;
  toggleTaskSelection: (taskId: string) => void;
  selectAllTasks: (taskIds: string[]) => void;
  clearTaskSelection: () => void;
  togglePmidSelection: (pmid: string) => void;
  clearPmidSelection: () => void;
  toggleTaskDetailExpand: (taskId: string) => void;
  togglePaperTaskExpand: (paperTaskId: string) => void;
  resetFilters: () => void;
}

const DEFAULT_FILTERS: UIFilters = {
  status: 'all',
  searchQuery: '',
  dateFilter: 'all',
};

export const createUISlice: StateCreator<UISlice> = (set, get) => ({
  taskFilters: { ...DEFAULT_FILTERS },
  requestFilters: { ...DEFAULT_FILTERS },
  selectedTaskIds: [],
  selectedPmids: [],
  expandedTaskDetails: new Set(),
  expandedPaperTasks: new Set(),
  
  setTaskFilter: (key, value) => {
    set(state => ({
      taskFilters: { ...state.taskFilters, [key]: value }
    }));
  },
  
  setRequestFilter: (key, value) => {
    set(state => ({
      requestFilters: { ...state.requestFilters, [key]: value }
    }));
  },
  
  toggleTaskSelection: (taskId) => {
    const { selectedTaskIds } = get();
    const newSelection = selectedTaskIds.includes(taskId)
      ? selectedTaskIds.filter(id => id !== taskId)
      : [...selectedTaskIds, taskId];
    set({ selectedTaskIds: newSelection });
  },
  
  selectAllTasks: (taskIds) => {
    set({ selectedTaskIds: taskIds });
  },
  
  clearTaskSelection: () => {
    set({ selectedTaskIds: [] });
  },
  
  togglePmidSelection: (pmid) => {
    const { selectedPmids } = get();
    const newSelection = selectedPmids.includes(pmid)
      ? selectedPmids.filter(id => id !== pmid)
      : [...selectedPmids, pmid];
    set({ selectedPmids: newSelection });
  },
  
  clearPmidSelection: () => {
    set({ selectedPmids: [] });
  },
  
  toggleTaskDetailExpand: (taskId) => {
    const { expandedTaskDetails } = get();
    const newSet = new Set(expandedTaskDetails);
    if (newSet.has(taskId)) {
      newSet.delete(taskId);
    } else {
      newSet.add(taskId);
    }
    set({ expandedTaskDetails: newSet });
  },
  
  togglePaperTaskExpand: (paperTaskId) => {
    const { expandedPaperTasks } = get();
    const newSet = new Set(expandedPaperTasks);
    if (newSet.has(paperTaskId)) {
      newSet.delete(paperTaskId);
    } else {
      newSet.add(paperTaskId);
    }
    set({ expandedPaperTasks: newSet });
  },
  
  resetFilters: () => {
    set({
      taskFilters: { ...DEFAULT_FILTERS },
      requestFilters: { ...DEFAULT_FILTERS },
    });
  },
});