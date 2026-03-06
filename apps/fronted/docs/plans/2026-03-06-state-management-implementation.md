# State Management Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor scattered component state into a centralized Zustand store with 3 slices, eliminating duplicate polling logic and establishing a single source of truth for task data.

**Architecture:** Single unified Zustand store with slice pattern. TaskSlice handles data fetching + polling. UISlice manages filters and selections. NotificationSlice provides global toast system.

**Tech Stack:** React 19, TypeScript, Zustand 5.0.10, Vite

---

## Phase 1: Core Infrastructure

### Task 1: Create Store Directory Structure

**Files:**
- Create: `src/stores/index.ts`
- Create: `src/stores/taskStore/index.ts`
- Create: `src/stores/taskStore/types.ts`
- Create: `src/stores/uiStore/index.ts`
- Create: `src/stores/notificationStore/index.ts`

**Step 1: Create directories**

```bash
mkdir -p src/stores/taskStore src/stores/uiStore src/stores/notificationStore
```

**Step 2: Create type definitions for TaskSlice**

Create `src/stores/taskStore/types.ts`:

```typescript
import type { 
  TaskListItem, 
  TaskStatusResponse, 
  TaskRequestStatusResponse,
  PubMedCandidateItem 
} from '../../types/api';

export interface TaskFilters {
  status?: string;
  searchQuery?: string;
  dateFilter?: string;
}

export interface PollingConfig {
  tasksListInterval: number;
  taskDetailInterval: number;
  requestInterval: number;
  maxPollingAttempts: number;
}

export interface TaskSliceState {
  // Task list
  tasks: TaskListItem[];
  tasksLoading: boolean;
  tasksError: string | null;
  lastTasksUpdate: Date | null;
  
  // Single task
  selectedTask: TaskStatusResponse | null;
  selectedTaskLoading: boolean;
  selectedTaskError: string | null;
  
  // Request
  currentRequest: TaskRequestStatusResponse | null;
  requestLoading: boolean;
  requestError: string | null;
  
  // Candidates
  candidates: PubMedCandidateItem[];
  candidatesLoading: boolean;
  candidatesError: string | null;
  
  // Polling
  pollingIntervals: Map<string, ReturnType<typeof setInterval>>;
  pollingConfig: PollingConfig;
}

export interface TaskSliceActions {
  fetchTasks: (filters?: TaskFilters) => Promise<void>;
  fetchTask: (taskId: string) => Promise<void>;
  fetchRequest: (requestId: string) => Promise<void>;
  fetchCandidates: (request: any) => Promise<void>;
  
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
```

**Step 3: Verify types compile**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 4: Commit**

```bash
git add src/stores/taskStore/types.ts
git commit -m "feat(stores): add TaskSlice type definitions"
```

---

### Task 2: Implement TaskSlice Core Actions

**Files:**
- Modify: `src/stores/taskStore/index.ts`

**Step 1: Write TaskSlice with basic fetch actions**

Create `src/stores/taskStore/index.ts`:

```typescript
import type { StateCreator } from 'zustand';
import type { TaskSlice, TaskFilters } from './types';
import { getTasks, getTaskStatus, getTaskRequestStatus } from '../../services/api';

const DEFAULT_POLLING_CONFIG = {
  tasksListInterval: 5000,
  taskDetailInterval: 2000,
  requestInterval: 3000,
  maxPollingAttempts: 300,
};

export const createTaskSlice: StateCreator<TaskSlice> = (set, get) => ({
  // Initial state
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
  
  // Actions
  fetchTasks: async (filters?: TaskFilters) => {
    set({ tasksLoading: true, tasksError: null });
    try {
      const response = await getTasks();
      let filteredTasks = response.items || [];
      
      // Apply filters if provided
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
      // Will implement when we have the API function
      set({ candidatesLoading: false });
    } catch (error: any) {
      set({ 
        candidatesError: error?.detail || 'Failed to fetch candidates', 
        candidatesLoading: false 
      });
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
    // Clear all polling intervals
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
  
  // Polling actions (will implement in next task)
  startTaskPolling: () => {},
  stopTaskPolling: () => {},
  startRequestPolling: () => {},
  stopRequestPolling: () => {},
  startTasksListPolling: () => {},
  stopTasksListPolling: () => {},
}));
```

**Step 2: Verify types compile**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add src/stores/taskStore/index.ts
git commit -m "feat(stores): implement TaskSlice core actions"
```

---

### Task 3: Implement Polling Logic

**Files:**
- Modify: `src/stores/taskStore/index.ts`

**Step 1: Add polling implementation**

Update `src/stores/taskStore/index.ts`, replace the empty polling actions:

```typescript
// Add these implementations to the slice:

startTaskPolling: (taskId: string) => {
  const { pollingIntervals, pollingConfig } = get();
  
  // Don't start if already polling
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
```

**Step 2: Verify types compile**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add src/stores/taskStore/index.ts
git commit -m "feat(stores): implement polling logic in TaskSlice"
```

---

### Task 4: Implement UISlice

**Files:**
- Create: `src/stores/uiStore/index.ts`

**Step 1: Write UISlice**

Create `src/stores/uiStore/index.ts`:

```typescript
import type { StateCreator } from 'zustand';

export interface UIFilters {
  status: string;
  searchQuery: string;
  dateFilter: string;
}

export interface UISlice {
  // Filters
  taskFilters: UIFilters;
  requestFilters: UIFilters;
  
  // Selection
  selectedTaskIds: string[];
  selectedPmids: string[];
  
  // Expansion
  expandedTaskDetails: Set<string>;
  expandedPaperTasks: Set<string>;
  
  // Actions
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
  // Initial state
  taskFilters: { ...DEFAULT_FILTERS },
  requestFilters: { ...DEFAULT_FILTERS },
  selectedTaskIds: [],
  selectedPmids: [],
  expandedTaskDetails: new Set(),
  expandedPaperTasks: new Set(),
  
  // Actions
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
```

**Step 2: Verify types compile**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add src/stores/uiStore/index.ts
git commit -m "feat(stores): implement UISlice for filters and selections"
```

---

### Task 5: Implement NotificationSlice

**Files:**
- Create: `src/stores/notificationStore/index.ts`

**Step 1: Write NotificationSlice**

Create `src/stores/notificationStore/index.ts`:

```typescript
import type { StateCreator } from 'zustand';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  timestamp: Date;
  autoDismiss: boolean;
  dismissAfter: number;
}

export interface NotificationSlice {
  notifications: Notification[];
  
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearAllNotifications: () => void;
  
  notifySuccess: (message: string) => void;
  notifyError: (message: string) => void;
  notifyWarning: (message: string) => void;
  notifyInfo: (message: string) => void;
}

export const createNotificationSlice: StateCreator<NotificationSlice> = (set, get) => ({
  notifications: [],
  
  addNotification: (notification) => {
    const id = `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newNotification: Notification = {
      ...notification,
      id,
      timestamp: new Date(),
    };
    
    set(state => ({
      notifications: [...state.notifications, newNotification]
    }));
    
    // Auto-dismiss after specified time
    if (notification.autoDismiss) {
      setTimeout(() => {
        get().removeNotification(id);
      }, notification.dismissAfter || 5000);
    }
  },
  
  removeNotification: (id) => {
    set(state => ({
      notifications: state.notifications.filter(n => n.id !== id)
    }));
  },
  
  clearAllNotifications: () => {
    set({ notifications: [] });
  },
  
  notifySuccess: (message) => {
    get().addNotification({
      type: 'success',
      message,
      autoDismiss: true,
      dismissAfter: 5000,
    });
  },
  
  notifyError: (message) => {
    get().addNotification({
      type: 'error',
      message,
      autoDismiss: true,
      dismissAfter: 7000,
    });
  },
  
  notifyWarning: (message) => {
    get().addNotification({
      type: 'warning',
      message,
      autoDismiss: true,
      dismissAfter: 6000,
    });
  },
  
  notifyInfo: (message) => {
    get().addNotification({
      type: 'info',
      message,
      autoDismiss: true,
      dismissAfter: 5000,
    });
  },
});
```

**Step 2: Verify types compile**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add src/stores/notificationStore/index.ts
git commit -m "feat(stores): implement NotificationSlice for global toasts"
```

---

### Task 6: Create Unified Store

**Files:**
- Create: `src/stores/index.ts`

**Step 1: Write unified store export**

Create `src/stores/index.ts`:

```typescript
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { createTaskSlice } from './taskStore';
import { createUISlice } from './uiStore';
import { createNotificationSlice } from './notificationStore';

// Unified store type
export type AppStore = ReturnType<typeof createAppStore>;

const createAppStore = create(
  devtools(
    (...a) => ({
      ...createTaskSlice(...a),
      ...createUISlice(...a),
      ...createNotificationSlice(...a),
    }),
    { name: 'MultiACMG-Store' }
  )
);

export const useAppStore = createAppStore;
```

**Step 2: Verify types compile**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add src/stores/index.ts
git commit -m "feat(stores): create unified Zustand store with DevTools"
```

---

## Phase 2: Component Migration

### Task 7: Create NotificationToast Component

**Files:**
- Create: `src/components/NotificationToast.tsx`
- Create: `src/components/NotificationToast.css`

**Step 1: Write NotificationToast component**

Create `src/components/NotificationToast.tsx`:

```typescript
import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { useAppStore } from '../stores';
import type { Notification } from '../stores/notificationStore';
import './NotificationToast.css';

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const Toast: React.FC<{
  notification: Notification;
  onClose: () => void;
}> = ({ notification, onClose }) => {
  const Icon = iconMap[notification.type];
  
  useEffect(() => {
    if (notification.autoDismiss) {
      const timer = setTimeout(onClose, notification.dismissAfter);
      return () => clearTimeout(timer);
    }
  }, [notification.autoDismiss, notification.dismissAfter, onClose]);
  
  return (
    <div className={`notification-toast notification-${notification.type}`}>
      <Icon className="notification-icon" size={20} />
      <span className="notification-message">{notification.message}</span>
      <button 
        className="notification-close" 
        onClick={onClose}
        aria-label="Close notification"
      >
        <X size={16} />
      </button>
    </div>
  );
};

export const NotificationToast: React.FC = () => {
  const notifications = useAppStore(s => s.notifications);
  const removeNotification = useAppStore(s => s.removeNotification);
  
  if (notifications.length === 0) return null;
  
  return (
    <div className="notification-container">
      {notifications.map(notification => (
        <Toast
          key={notification.id}
          notification={notification}
          onClose={() => removeNotification(notification.id)}
        />
      ))}
    </div>
  );
};
```

**Step 2: Write CSS**

Create `src/components/NotificationToast.css`:

```css
.notification-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 400px;
}

.notification-toast {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  animation: slideIn 0.3s ease-out;
}

.notification-success {
  border-left: 4px solid #10b981;
}

.notification-error {
  border-left: 4px solid #ef4444;
}

.notification-warning {
  border-left: 4px solid #f59e0b;
}

.notification-info {
  border-left: 4px solid #3b82f6;
}

.notification-icon {
  flex-shrink: 0;
}

.notification-success .notification-icon {
  color: #10b981;
}

.notification-error .notification-icon {
  color: #ef4444;
}

.notification-warning .notification-icon {
  color: #f59e0b;
}

.notification-info .notification-icon {
  color: #3b82f6;
}

.notification-message {
  flex: 1;
  font-size: 14px;
  color: #333;
}

.notification-close {
  flex-shrink: 0;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: #666;
  transition: color 0.2s;
}

.notification-close:hover {
  color: #333;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
```

**Step 3: Add to main.tsx**

Modify `src/main.tsx`, add NotificationToast:

```typescript
import { NotificationToast } from './components/NotificationToast';

// In the render, add NotificationToast at the top level:
root.render(
  <React.StrictMode>
    <NotificationToast />
    <App />
  </React.StrictMode>
);
```

**Step 4: Verify types compile**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 5: Commit**

```bash
git add src/components/NotificationToast.tsx src/components/NotificationToast.css src/main.tsx
git commit -m "feat(components): add NotificationToast component for global notifications"
```

---

### Task 8: Refactor TaskStatusPage

**Files:**
- Modify: `src/pages/TaskStatusPage.tsx`

**Step 1: Replace useState with store**

Replace all state management in TaskStatusPage with store hooks. The component should go from ~383 lines to ~150 lines.

**Step 2: Test manually**

- Navigate to task detail page
- Verify polling starts automatically
- Verify data loads correctly
- Verify polling stops on terminal status
- Verify auto-redirect works

**Step 3: Commit**

```bash
git add src/pages/TaskStatusPage.tsx
git commit -m "refactor(pages): migrate TaskStatusPage to use Zustand store"
```

---

### Task 9: Refactor RequestMonitorPage

**Files:**
- Modify: `src/pages/tasks/RequestMonitorPage.tsx`

**Step 1: Replace useState with store**

Replace all state management in RequestMonitorPage with store hooks. The component should go from ~434 lines to ~180 lines.

**Step 2: Test manually**

- Navigate to request monitor page
- Verify polling starts automatically
- Verify data loads correctly
- Verify polling stops on terminal status
- Verify expansion state works

**Step 3: Commit**

```bash
git add src/pages/tasks/RequestMonitorPage.tsx
git commit -m "refactor(pages): migrate RequestMonitorPage to use Zustand store"
```

---

### Task 10: Refactor TasksPage

**Files:**
- Modify: `src/pages/TasksPage.tsx`

**Step 1: Replace useState with store**

Replace all 9 useState calls with store hooks. The component should go from ~709 lines to ~250 lines.

**Step 2: Test manually**

- Navigate to tasks list page
- Verify data loads correctly
- Verify polling starts when processing tasks exist
- Verify filters work
- Verify selection state works
- Verify notifications trigger on status changes

**Step 3: Commit**

```bash
git add src/pages/TasksPage.tsx
git commit -m "refactor(pages): migrate TasksPage to use Zustand store"
```

---

## Phase 3: Validation & Cleanup

### Task 11: Run Lint and Type Checks

**Step 1: Run lint**

```bash
npm run lint
```

Fix all issues.

**Step 2: Run type check**

```bash
npx tsc --noEmit
```

Fix all type errors.

**Step 3: Commit**

```bash
git add .
git commit -m "chore: fix lint and type errors from state management refactor"
```

---

### Task 12: Manual E2E Testing

**Test Checklist**:

1. **TaskStatusPage**:
   - [ ] Page loads correctly
   - [ ] Data fetches successfully
   - [ ] Polling starts automatically
   - [ ] Polling stops on SUCCESS/FAILURE/REVOKED
   - [ ] Auto-redirect works on SUCCESS
   - [ ] Polling stops on component unmount

2. **RequestMonitorPage**:
   - [ ] Page loads correctly
   - [ ] Data fetches successfully
   - [ ] Polling starts automatically
   - [ ] Polling stops on success/failed/partial_failed
   - [ ] Expansion state works
   - [ ] Polling stops on component unmount

3. **TasksPage**:
   - [ ] Page loads correctly
   - [ ] Data fetches successfully
   - [ ] Polling starts when processing tasks exist
   - [ ] Polling stops when all tasks are terminal
   - [ ] Filters work correctly
   - [ ] Selection state works
   - [ ] Notifications trigger on status changes
   - [ ] Polling stops on component unmount

4. **Cross-page tests**:
   - [ ] Navigate between pages while polling is active
   - [ ] Verify no memory leaks (check React DevTools)
   - [ ] Verify notifications appear from all pages

---

### Task 13: Update Documentation

**Files:**
- Modify: `AGENTS.md`

**Step 1: Add store usage documentation**

Add section to AGENTS.md:

```markdown
## 13. State Management

**Library**: Zustand 5.0.10

**Architecture**: Single unified store with slices

**Usage**:
```typescript
import { useAppStore } from '@/stores';

// In component
const { tasks, fetchTasks } = useAppStore();
const taskFilters = useAppStore(s => s.taskFilters);
```

**Slices**:
- TaskSlice: Task data, requests, candidates, polling
- UISlice: Filters, selections, expansion state
- NotificationSlice: Global toast notifications

**DevTools**: Install Redux DevTools extension to inspect store state.
```

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add state management documentation to AGENTS.md"
```

---

## Completion Checklist

**Phase 1 Complete When**:
- [ ] All slice files created
- [ ] Unified store exports correctly
- [ ] Type checks pass
- [ ] Lint passes

**Phase 2 Complete When**:
- [ ] All 3 pages refactored
- [ ] Manual testing passes
- [ ] No regressions

**Phase 3 Complete When**:
- [ ] Lint passes
- [ ] Type checks pass
- [ ] E2E manual testing complete
- [ ] Documentation updated
- [ ] No memory leaks detected

**Final Success Criteria**:
- [ ] Component line count reduced by 60%+
- [ ] Polling duplication eliminated
- [ ] Single source of truth for task data
- [ ] Cross-page notifications working
- [ ] All tests passing