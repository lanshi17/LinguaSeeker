# State Management Refactoring Plan

**Date**: 2026-03-06  
**Priority**: Highest (系统可靠性基石)  
**Status**: Planning Complete, Ready for Implementation  
**Estimated Effort**: 4-5 days

---

## 1. Problem Statement

### 1.1 Current Issues

**Polling Duplication (3 different implementations)**:
- `TasksPage.tsx`: `setInterval` pattern (5s interval), `useRef` for cleanup
- `RequestMonitorPage.tsx`: `setTimeout` recursion (3s interval), auto-stops on terminal
- `TaskStatusPage.tsx`: `setTimeout` recursion (2s interval), auto-redirect on success

**State Duplication**:
- Loading state: `loading` / `isLoading` / `loading` (all pages)
- Error state: `error` / `error` / `error` (all pages)
- Data state: `tasks[]` / `requestData` / `task` (all pages)
- Poll count: `pollingCount` (implicit or explicit)

**Data Flow Issues**:
- No caching: each page fetches independently
- No sharing: TasksPage fetches list, TaskStatusPage fetches single task (no reuse)
- N+1 problem: list view doesn't prefetch details
- No optimistic updates: mutations only update local state

**Missing Global State**:
- No cross-page notifications
- No connection status tracking
- No request deduplication
- Filter preferences lost on navigation

### 1.2 Impact

- **Developer Experience**: High cognitive load, duplicated logic
- **User Experience**: Inconsistent state, no cross-page notifications
- **Maintainability**: Changes require updating multiple files
- **Performance**: Potential memory leaks, redundant API calls

---

## 2. Solution Architecture

### 2.1 Technology Choice

**Zustand 5.0.10** (already installed)

**Why Zustand**:
- Simple API, no boilerplate
- TypeScript-first design
- Built-in devtools middleware
- Easy testing
- No providers needed
- Small bundle size (~1KB)

**Architecture Pattern**: Single unified store with slices

```typescript
// Slice pattern
const createTaskSlice: StateCreator<TaskSlice> = (set, get) => ({
  // state
  tasks: [],
  // actions
  fetchTasks: async () => { ... }
});

// Unified store
const useAppStore = create(
  devtools((...a) => ({
    ...createTaskSlice(...a),
    ...createUISlice(...a),
    ...createNotificationSlice(...a),
  }))
);
```

### 2.2 Store Structure

```
src/stores/
├── index.ts              # Export unified store
├── taskStore/
│   ├── index.ts         # Task slice
│   ├── types.ts         # Task slice types
│   └── actions.ts       # Task actions
├── uiStore/
│   └── index.ts         # UI slice
└── notificationStore/
    └── index.ts         # Notification slice
```

---

## 3. Slice Designs

### 3.1 TaskSlice (Most Complex)

**Responsibilities**:
- Task list management
- Single task detail
- Request monitoring
- Candidate selection
- Polling orchestration

**State Shape**:
```typescript
interface TaskSlice {
  // Task list data
  tasks: TaskListItem[];
  tasksLoading: boolean;
  tasksError: string | null;
  lastTasksUpdate: Date | null;
  
  // Single task detail
  selectedTask: TaskStatusResponse | null;
  selectedTaskLoading: boolean;
  selectedTaskError: string | null;
  
  // Request monitoring
  currentRequest: TaskRequestStatusResponse | null;
  requestLoading: boolean;
  requestError: string | null;
  
  // Candidates
  candidates: PubMedCandidateItem[];
  candidatesLoading: boolean;
  candidatesError: string | null;
  
  // Polling control
  pollingIntervals: Map<string, number>;
  pollingConfig: {
    tasksListInterval: 5000;
    taskDetailInterval: 2000;
    requestInterval: 3000;
    maxPollingAttempts: 300;
  };
  
  // Actions (see implementation plan)
  fetchTasks: (filters?) => Promise<void>;
  fetchTask: (taskId) => Promise<void>;
  fetchRequest: (requestId) => Promise<void>;
  fetchCandidates: (request) => Promise<void>;
  
  startTaskPolling: (taskId) => void;
  stopTaskPolling: (taskId) => void;
  startRequestPolling: (requestId) => void;
  stopRequestPolling: (requestId) => void;
  startTasksListPolling: () => void;
  stopTasksListPolling: () => void;
  
  createTask: (request) => Promise<TaskCreateResponse>;
  cancelTask: (taskId) => Promise<void>;
  selectCandidates: (requestId, pmids) => Promise<void>;
  
  clearSelectedTask: () => void;
  clearRequest: () => void;
  reset: () => void;
}
```

**Polling Strategy**:

1. **TasksList Polling** (TasksPage):
   - Start: When component mounts
   - Continue: While ANY task is in processing state
   - Stop: When all tasks are terminal OR component unmounts
   - Interval: 5000ms

2. **TaskDetail Polling** (TaskStatusPage):
   - Start: When navigating to task detail
   - Continue: Until task reaches terminal status
   - Stop: On terminal status OR component unmount
   - Interval: 2000ms
   - Special: Auto-redirect on SUCCESS after 1.5s

3. **Request Polling** (RequestMonitorPage):
   - Start: When viewing request details
   - Continue: Until request reaches terminal status
   - Stop: On terminal status OR component unmount
   - Interval: 3000ms

**Status Change Detection**:
```typescript
// Detect transitions for notifications
const prevTask = get().selectedTask;
const newTask = await api.getTaskStatus(taskId);

if (prevTask?.status === 'processing' && newTask.status === 'SUCCESS') {
  useAppStore.getState().notifySuccess('Task completed!');
}
```

### 3.2 UISlice

**Responsibilities**:
- Task list filters
- Request filters
- Selection state (multi-select)
- Expansion state

**State Shape**:
```typescript
interface UISlice {
  // Filters
  taskFilters: {
    status: TaskStatus | 'all';
    searchQuery: string;
    dateFilter: 'all' | 'today' | 'week' | 'month';
  };
  
  requestFilters: {
    status: RequestStatus | 'all';
    searchQuery: string;
  };
  
  // Selection
  selectedTaskIds: string[];
  selectedPmids: string[];
  
  // Expansion
  expandedTaskDetails: Set<string>;
  expandedPaperTasks: Set<string>;
  
  // Actions
  setTaskFilter: (key, value) => void;
  setRequestFilter: (key, value) => void;
  toggleTaskSelection: (taskId) => void;
  selectAllTasks: (taskIds) => void;
  clearTaskSelection: () => void;
  togglePmidSelection: (pmid) => void;
  toggleTaskDetailExpand: (taskId) => void;
  togglePaperTaskExpand: (paperTaskId) => void;
  resetFilters: () => void;
}
```

**No Persistence**: State resets on page refresh (can add zustand/middleware/persist later)

### 3.3 NotificationSlice

**Responsibilities**:
- Global toast notifications
- Auto-dismiss logic
- Type-based styling

**State Shape**:
```typescript
interface NotificationSlice {
  notifications: Array<{
    id: string;
    type: 'success' | 'error' | 'warning' | 'info';
    message: string;
    timestamp: Date;
    autoDismiss: boolean;
    dismissAfter: number;
  }>;
  
  // Actions
  addNotification: (notification) => void;
  removeNotification: (id) => void;
  clearAllNotifications: () => void;
  
  // Helpers
  notifySuccess: (message) => void;
  notifyError: (message) => void;
  notifyWarning: (message) => void;
  notifyInfo: (message) => void;
}
```

**UI Component**:
```typescript
// src/components/NotificationToast.tsx
const NotificationToast = () => {
  const notifications = useAppStore(s => s.notifications);
  const remove = useAppStore(s => s.removeNotification);
  
  return (
    <div className="notification-container">
      {notifications.map(n => (
        <Toast key={n.id} {...n} onClose={() => remove(n.id)} />
      ))}
    </div>
  );
};
```

---

## 4. Migration Strategy

### 4.1 Phase 1: Core Infrastructure (Day 1-2)

**Tasks**:
1. Create store directory structure
2. Implement TaskSlice with basic actions
3. Implement UISlice
4. Implement NotificationSlice
5. Create unified store export
6. Add DevTools middleware

**Files to Create**:
- `src/stores/index.ts`
- `src/stores/taskStore/index.ts`
- `src/stores/taskStore/types.ts`
- `src/stores/uiStore/index.ts`
- `src/stores/notificationStore/index.ts`
- `src/components/NotificationToast.tsx`

**Testing**:
- Manual testing in browser
- DevTools inspection
- Console logging for polling lifecycle

### 4.2 Phase 2: Component Migration (Day 3-4)

**Migration Order** (risk-based):
1. **TaskStatusPage** (simplest, validates polling)
2. **RequestMonitorPage** (medium complexity)
3. **TasksPage** (most complex, validates all patterns)

**Migration Pattern**:
```typescript
// Before (709 lines with 9 useState)
const [tasks, setTasks] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);
// ... 6 more useState
// ... polling logic
// ... change detection

// After (~200 lines)
const {
  tasks, tasksLoading, tasksError, lastTasksUpdate,
  fetchTasks, startTasksListPolling, stopTasksListPolling
} = useAppStore();
const {
  taskFilters, selectedTaskIds, setTaskFilter, toggleTaskSelection
} = useAppStore();

useEffect(() => {
  fetchTasks();
  startTasksListPolling();
  return () => stopTasksListPolling();
}, []);
```

**Testing Checklist for Each Page**:
- [ ] Page loads correctly
- [ ] Data fetches successfully
- [ ] Polling starts automatically
- [ ] Polling stops on terminal status
- [ ] Polling stops on component unmount
- [ ] Filters work correctly
- [ ] Selection state works
- [ ] Error states display
- [ ] Loading states display
- [ ] Notifications trigger on status changes

### 4.3 Phase 3: Validation & Cleanup (Day 5)

**Tasks**:
1. Run `npm run lint` - fix all issues
2. Run `npx tsc --noEmit` - fix type errors
3. Manual E2E testing of all task flows
4. Check for memory leaks (React DevTools)
5. Verify polling behavior with network throttling
6. Remove deprecated code from `taskApi.ts` (if applicable)
7. Update documentation

---

## 5. Benefits & Trade-offs

### 5.1 Benefits

**Developer Experience**:
- ✅ Reduce component complexity (709 → 200 lines)
- ✅ Single source of truth for task data
- ✅ Easier testing (mock store instead of API)
- ✅ Better separation of concerns

**User Experience**:
- ✅ Cross-page notifications
- ✅ Consistent state across views
- ✅ No lost filter preferences
- ✅ Faster perceived performance (optimistic updates ready)

**Maintainability**:
- ✅ Eliminates 3 duplicate polling implementations
- ✅ Centralized error handling
- ✅ Foundation for future features (caching, optimistic updates)

### 5.2 Trade-offs

**Added Complexity**:
- ⚠️ New learning curve for Zustand
- ⚠️ Additional abstraction layer
- ⚠️ More files to maintain

**Migration Risk**:
- ⚠️ Potential for regressions during refactor
- ⚠️ Requires thorough testing
- ⚠️ May need to fix existing bugs discovered

**No Persistence**:
- ⚠️ State lost on page refresh
- ⚠️ Can add later with `persist` middleware

---

## 6. Future Enhancements (Post Phase 1)

**Phase 2: Advanced Features**
- Optimistic updates for mutations
- Request caching with TTL
- Offline support with retry queue
- WebSocket integration for real-time updates

**Phase 3: Persistence**
- Add `zustand/middleware/persist` for user preferences
- Store filter preferences in localStorage
- Store session token (if needed)

**Phase 4: Testing**
- Unit tests for all store actions
- Integration tests for polling logic
- E2E tests for complete flows

---

## 7. Success Criteria

**Phase 1 Complete When**:
- [ ] All 3 slices implemented and working
- [ ] All 3 pages refactored to use store
- [ ] All polling logic working correctly
- [ ] `npm run lint` passes with no errors
- [ ] `npx tsc --noEmit` passes with no errors
- [ ] Manual E2E testing passes all scenarios
- [ ] No memory leaks detected
- [ ] Documentation updated

**Metrics**:
- Component lines of code: -65% (709 → ~200 for TasksPage)
- Duplicate polling logic: -100% (3 → 0 implementations)
- State-related bugs: Baseline established for tracking

---

## 8. Risks & Mitigation

**Risk 1: Polling Behavior Regression**
- Mitigation: Thorough testing with network throttling
- Mitigation: Add logging for polling lifecycle events
- Mitigation: Keep old code in git history for reference

**Risk 2: Type Safety Issues**
- Mitigation: Run `tsc --noEmit` after each file change
- Mitigation: Use strict TypeScript patterns in store
- Mitigation: Add JSDoc for complex types

**Risk 3: Performance Degradation**
- Mitigation: Use selectors to prevent unnecessary re-renders
- Mitigation: Profile with React DevTools before/after
- Mitigation: Keep polling intervals reasonable

**Risk 4: Scope Creep**
- Mitigation: Stick to Phase 1 scope only
- Mitigation: Document future enhancements separately
- Mitigation: Resist temptation to add persistence now

---

## 9. Implementation Checklist

See separate implementation plan document for detailed task breakdown.

---

## 10. Appendix

### 10.1 Type Definitions Reference

See `src/types/api.ts` for existing types:
- `TaskListItem`
- `TaskStatusResponse`
- `TaskRequestStatusResponse`
- `PubMedCandidateItem`
- `TaskFilters` (to be created)

### 10.2 API Functions Reference

See `src/services/api.ts` for existing functions:
- `getTasks()`
- `getTaskStatus(taskId)`
- `createTaskRequestByUpload()`
- `searchPubMedCandidates()`
- `submitPubMedSelection()`
- `getTaskRequestStatus()`

### 10.3 Related Documentation

- [AGENTS.md](../AGENTS.md) - Project coding guidelines
- [PRD.md](../../PRD.md) - Product requirements
- [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) - Overall implementation plan