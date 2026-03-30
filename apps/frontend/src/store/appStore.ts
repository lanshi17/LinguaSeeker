import { create } from 'zustand';

import { pubmedCandidateSearch, getTaskRequestStatus } from '../services/api';

import type {
  PubMedCandidateItem,
  PubMedCandidateSearchRequest,
  TaskRequestStatusResponse,
} from '../types/api';

type TaskFilters = {
  status?: string;
  searchQuery?: string;
  dateFilter?: string;
};

type PollingConfig = {
  requestInterval: number;
};

type UIState = {
  taskFilters: TaskFilters;
  requestFilters: TaskFilters;
  selectedPmids: string[];
  expandedPaperTasks: string[];
};

type AppStoreState = {
  currentRequest: TaskRequestStatusResponse | null;
  requestLoading: boolean;
  requestError: string | null;
  candidates: PubMedCandidateItem[];
  candidatesLoading: boolean;
  candidatesError: string | null;
  pollingIntervals: Map<string, ReturnType<typeof setInterval>>;
  pollingConfig: PollingConfig;
  ui: UIState;
};

type AppStoreActions = {
  fetchRequest: (requestId: string) => Promise<void>;
  fetchCandidates: (payload: PubMedCandidateSearchRequest) => Promise<void>;
  startRequestPolling: (requestId: string) => void;
  stopRequestPolling: (requestId: string) => void;
  setTaskFilter: (key: keyof TaskFilters, value: string) => void;
  setRequestFilter: (key: keyof TaskFilters, value: string) => void;
  togglePmidSelection: (pmid: string) => void;
  clearPmidSelection: () => void;
  togglePaperTaskExpand: (paperTaskId: string) => void;
  reset: () => void;
};

export type AppStore = AppStoreState & AppStoreActions;

const DEFAULT_FILTERS: TaskFilters = {
  status: 'all',
  searchQuery: '',
  dateFilter: 'all',
};

const DEFAULT_POLLING_CONFIG: PollingConfig = {
  requestInterval: 2000,
};

const initialUiState = (): UIState => ({
  taskFilters: { ...DEFAULT_FILTERS },
  requestFilters: { ...DEFAULT_FILTERS },
  selectedPmids: [],
  expandedPaperTasks: [],
});

export const useAppStore = create<AppStore>((set, get) => ({
  currentRequest: null,
  requestLoading: false,
  requestError: null,
  candidates: [],
  candidatesLoading: false,
  candidatesError: null,
  pollingIntervals: new Map(),
  pollingConfig: DEFAULT_POLLING_CONFIG,
  ui: initialUiState(),

  fetchRequest: async (requestId: string) => {
    set({ requestLoading: true, requestError: null });
    try {
      const request = await getTaskRequestStatus(requestId);
      set({ currentRequest: request, requestLoading: false, requestError: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch request';
      set({ requestError: message, requestLoading: false });
    }
  },

  fetchCandidates: async (payload: PubMedCandidateSearchRequest) => {
    set({ candidatesLoading: true, candidatesError: null });
    try {
      const response = await pubmedCandidateSearch(payload);
      set({ candidates: response.candidates ?? [], candidatesLoading: false, candidatesError: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch candidates';
      set({ candidatesError: message, candidatesLoading: false });
    }
  },

  startRequestPolling: (requestId: string) => {
    const { pollingIntervals, pollingConfig } = get();
    const key = `request-${requestId}`;
    if (pollingIntervals.has(key)) {
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

    set({ pollingIntervals: new Map(pollingIntervals).set(key, intervalId) });
  },

  stopRequestPolling: (requestId: string) => {
    const { pollingIntervals } = get();
    const key = `request-${requestId}`;
    const intervalId = pollingIntervals.get(key);
    if (!intervalId) {
      return;
    }

    clearInterval(intervalId);
    const nextIntervals = new Map(pollingIntervals);
    nextIntervals.delete(key);
    set({ pollingIntervals: nextIntervals });
  },

  setTaskFilter: (key, value) => {
    set((state) => ({
      ui: {
        ...state.ui,
        taskFilters: {
          ...state.ui.taskFilters,
          [key]: value,
        },
      },
    }));
  },

  setRequestFilter: (key, value) => {
    set((state) => ({
      ui: {
        ...state.ui,
        requestFilters: {
          ...state.ui.requestFilters,
          [key]: value,
        },
      },
    }));
  },

  togglePmidSelection: (pmid) => {
    set((state) => {
      const exists = state.ui.selectedPmids.includes(pmid);
      return {
        ui: {
          ...state.ui,
          selectedPmids: exists
            ? state.ui.selectedPmids.filter((item) => item !== pmid)
            : [...state.ui.selectedPmids, pmid],
        },
      };
    });
  },

  clearPmidSelection: () => {
    set((state) => ({
      ui: {
        ...state.ui,
        selectedPmids: [],
      },
    }));
  },

  togglePaperTaskExpand: (paperTaskId) => {
    set((state) => {
      const exists = state.ui.expandedPaperTasks.includes(paperTaskId);
      return {
        ui: {
          ...state.ui,
          expandedPaperTasks: exists
            ? state.ui.expandedPaperTasks.filter((item) => item !== paperTaskId)
            : [...state.ui.expandedPaperTasks, paperTaskId],
        },
      };
    });
  },

  reset: () => {
    const { pollingIntervals } = get();
    pollingIntervals.forEach((intervalId) => {
      clearInterval(intervalId);
    });
    set({
      currentRequest: null,
      requestLoading: false,
      requestError: null,
      candidates: [],
      candidatesLoading: false,
      candidatesError: null,
      pollingIntervals: new Map(),
      pollingConfig: DEFAULT_POLLING_CONFIG,
      ui: initialUiState(),
    });
  },
}));
