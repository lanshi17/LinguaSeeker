# Agent-Interactive Platform Architecture Refactoring Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the current HTTP polling-based React frontend into a LangGraph-powered agent-interactive platform with real-time streaming, workflow visualization, and human-in-the-loop capabilities.

**Architecture:** Migrate from HTTP polling to WebSocket/SSE for real-time state synchronization. Implement a LangGraph-aware state management layer that mirrors backend StateGraph execution. Create conversational UI components for agent interaction, workflow visualization components for multi-step pipeline transparency, and human-in-the-loop decision panels for expert arbitration.

**Tech Stack:** React 19, TypeScript, Zustand, LangGraph SDK (@langchain/langgraph-sdk), WebSocket/SSE, Framer Motion (animations), rc-steps (workflow timeline), react-force-graph (knowledge graph visualization)

---

## Phase 1: Foundation Infrastructure

### Task 1.1: Install Dependencies

**Files:**
- Modify: `package.json`

**Step 1: Install LangGraph SDK and streaming libraries**

```bash
npm install @langchain/langgraph-sdk
npm install socket.io-client  # WebSocket client
npm install eventsource-parser # SSE parser (fallback)
```

**Step 2: Install UI enhancement libraries**

```bash
npm install framer-motion     # Animations
npm install rc-steps          # Workflow timeline
npm install react-force-graph # Graph visualization (for KG query workflow)
```

**Step 3: Verify installation**

Run: `npm list @langchain/langgraph-sdk socket.io-client`
Expected: Versions displayed without errors

**Step 4: Update TypeScript types**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 5: Commit**

```bash
git add package.json package-lock.json
git commit -m "deps: add LangGraph SDK and streaming dependencies"
```

---

### Task 1.2: Create WebSocket Service Layer

**Files:**
- Create: `src/services/websocket.ts`
- Create: `src/types/stream.ts`

**Step 1: Define stream event types**

Create `src/types/stream.ts`:

```typescript
// LangGraph stream event types
export type StreamEventType =
  | 'on_chat_model_stream'     // P0.0 agent conversation
  | 'on_chain_start'            // Node execution start
  | 'on_chain_end'              // Node execution complete
  | 'on_chain_error'            // Node execution error
  | 'on_custom_event';          // Custom business events

export interface StreamEvent {
  event: StreamEventType;
  data?: any;
  metadata?: {
    langgraph_node?: string;    // Node ID from LangGraph
    langgraph_checkpoint_id?: string;
    run_id?: string;
  };
  timestamp?: string;
}

// Node-to-frontend step mapping
export type WorkflowNodeId =
  | 'clarification_agent'        // P0.0
  | 'literature_agent'           // P1.0
  | 'parsing_agent'              // P2.0 (MinerU)
  | 'translation_agent'          // P3.0
  | 'extraction_agent'           // P4.0
  | 'acmg_classifier'            // P5.0
  | 'expert_arbitrator';         // Human-in-the-loop

export type FrontendStepId =
  | 'clarification'
  | 'literature'
  | 'parsing'
  | 'translation'
  | 'extraction'
  | 'classification'
  | 'arbitration';

export const NODE_TO_STEP_MAP: Record<WorkflowNodeId, FrontendStepId> = {
  clarification_agent: 'clarification',
  literature_agent: 'literature',
  parsing_agent: 'parsing',
  translation_agent: 'translation',
  extraction_agent: 'extraction',
  acmg_classifier: 'classification',
  expert_arbitrator: 'arbitration',
};

// Custom event types
export interface HumanFeedbackRequiredEvent {
  type: 'HUMAN_FEEDBACK_REQUIRED';
  payload: {
    reason: string;
    current_value: any;
    options?: any[];
    paper_task_id: string;
  };
}

export interface ProgressUpdateEvent {
  type: 'PROGRESS_UPDATE';
  payload: {
    paper_task_id: string;
    step: FrontendStepId;
    progress: number;  // 0-100
    message?: string;
  };
}

export type CustomEventPayload = HumanFeedbackRequiredEvent | ProgressUpdateEvent;
```

**Step 2: Create WebSocket service**

Create `src/services/websocket.ts`:

```typescript
import { io, Socket } from 'socket.io-client';
import type { StreamEvent, CustomEventPayload } from '../types/stream';

type EventCallback = (event: StreamEvent) => void;

class WebSocketService {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000;
  private listeners: Map<string, Set<EventCallback>> = new Map();

  connect(threadId?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
      
      this.socket = io(wsUrl, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: this.maxReconnectAttempts,
        reconnectionDelay: this.reconnectDelay,
        query: threadId ? { thread_id: threadId } : {},
      });

      this.socket.on('connect', () => {
        console.log('[WebSocket] Connected to backend');
        this.reconnectAttempts = 0;
        resolve();
      });

      this.socket.on('connect_error', (error) => {
        console.error('[WebSocket] Connection error:', error);
        this.reconnectAttempts++;
        
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          reject(new Error('Max reconnection attempts reached'));
        }
      });

      this.socket.on('disconnect', (reason) => {
        console.warn('[WebSocket] Disconnected:', reason);
      });

      // Listen to LangGraph stream events
      this.socket.on('stream_event', (event: StreamEvent) => {
        this.notifyListeners('stream_event', event);
      });

      // Listen to custom business events
      this.socket.on('custom_event', (event: CustomEventPayload) => {
        this.notifyListeners('custom_event', event);
      });
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.listeners.clear();
    }
  }

  subscribe(eventType: string, callback: EventCallback): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);

    // Return unsubscribe function
    return () => {
      const callbacks = this.listeners.get(eventType);
      if (callbacks) {
        callbacks.delete(callback);
      }
    };
  }

  private notifyListeners(eventType: string, event: any): void {
    const callbacks = this.listeners.get(eventType);
    if (callbacks) {
      callbacks.forEach(callback => callback(event));
    }
  }

  // Send user feedback for human-in-the-loop
  sendFeedback(data: {
    thread_id: string;
    node: string;
    action: 'confirm' | 'reject' | 'modify';
    payload: any;
  }): void {
    if (!this.socket) {
      throw new Error('WebSocket not connected');
    }
    this.socket.emit('human_feedback', data);
  }

  isConnected(): boolean {
    return this.socket?.connected ?? false;
  }
}

export const wsService = new WebSocketService();
```

**Step 3: Test WebSocket connectivity**

Manual test (after backend implements WebSocket endpoint):
1. Start backend: `cd ../../backend && uvicorn main:app --reload`
2. Start frontend: `npm run dev`
3. Open browser console
4. Run: `wsService.connect()`
5. Expected: "[WebSocket] Connected to backend"

**Step 4: Add environment variables**

Add to `.env.development`:
```
VITE_WS_URL=ws://localhost:8000
```

Add to `.env.production`:
```
VITE_WS_URL=wss://your-production-domain.com
```

**Step 5: Commit**

```bash
git add src/services/websocket.ts src/types/stream.ts .env.development .env.production
git commit -m "feat: add WebSocket service layer for LangGraph streaming"
```

---

### Task 1.3: Create LangGraph-Aware Workflow Store

**Files:**
- Create: `src/stores/workflowStore/types.ts`
- Create: `src/stores/workflowStore/index.ts`

**Step 1: Define workflow state types**

Create `src/stores/workflowStore/types.ts`:

```typescript
import type { FrontendStepId } from '../../types/stream';

export type StepStatus = 'pending' | 'running' | 'completed' | 'error' | 'waiting_input';

export interface WorkflowStep {
  id: FrontendStepId;
  label: string;
  description?: string;
  status: StepStatus;
  output?: any;           // Node execution output
  logs?: string[];        // Execution logs
  progress?: number;      // 0-100 for long-running tasks (parsing)
  startTime?: Date;
  endTime?: Date;
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    step_id?: FrontendStepId;
    paper_task_id?: string;
  };
}

export interface PaperTaskState {
  paper_task_id: string;
  pmid?: string;
  filename?: string;
  currentStep: FrontendStepId;
  steps: WorkflowStep[];
  status: 'queued' | 'running' | 'success' | 'failed';
  error?: string;
}

export interface WorkflowState {
  // Connection state
  isConnected: boolean;
  isStreaming: boolean;
  threadId: string | null;

  // Request-level state (aggregated)
  requestId: string | null;
  requestStatus: 'queued' | 'running' | 'partial_failed' | 'failed' | 'success' | null;
  
  // Paper-level states
  paperTasks: Map<string, PaperTaskState>;
  
  // Conversation history (P0.0 clarification)
  messages: ConversationMessage[];
  
  // Human-in-the-loop
  pendingFeedback: {
    paper_task_id: string;
    reason: string;
    current_value: any;
    options?: any[];
  } | null;

  // Actions
  connect: (threadId?: string) => Promise<void>;
  disconnect: () => void;
  updateStepStatus: (paperTaskId: string, stepId: FrontendStepId, status: StepStatus, output?: any) => void;
  addLog: (paperTaskId: string, stepId: FrontendStepId, log: string) => void;
  updateProgress: (paperTaskId: string, stepId: FrontendStepId, progress: number) => void;
  addMessage: (message: Omit<ConversationMessage, 'id' | 'timestamp'>) => void;
  setPendingFeedback: (feedback: WorkflowState['pendingFeedback']) => void;
  submitFeedback: (action: 'confirm' | 'reject' | 'modify', payload?: any) => void;
  reset: () => void;
}
```

**Step 2: Implement workflow store**

Create `src/stores/workflowStore/index.ts`:

```typescript
import { create } from 'zustand';
import { wsService } from '../../services/websocket';
import type { StreamEvent, CustomEventPayload, NODE_TO_STEP_MAP } from '../../types/stream';
import type { WorkflowState, WorkflowStep, PaperTaskState } from './types';

const INITIAL_STEPS: WorkflowStep[] = [
  { id: 'clarification', label: '需求澄清 (P0.0)', status: 'pending' },
  { id: 'literature', label: '文献获取 (P1.0)', status: 'pending' },
  { id: 'parsing', label: '文档解析 (P2.0 - MinerU)', status: 'pending' },
  { id: 'translation', label: '多语言处理 (P3.0)', status: 'pending' },
  { id: 'extraction', label: '证据提取 (P4.0)', status: 'pending' },
  { id: 'classification', label: 'ACMG 判定 (P5.0)', status: 'pending' },
  { id: 'arbitration', label: '专家裁决', status: 'pending' },
];

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  // Initial state
  isConnected: false,
  isStreaming: false,
  threadId: null,
  requestId: null,
  requestStatus: null,
  paperTasks: new Map(),
  messages: [],
  pendingFeedback: null,

  // Actions
  connect: async (threadId?: string) => {
    try {
      await wsService.connect(threadId);
      set({ isConnected: true, threadId: threadId || null });

      // Subscribe to stream events
      wsService.subscribe('stream_event', (event: StreamEvent) => {
        handleStreamEvent(event, set, get);
      });

      // Subscribe to custom events
      wsService.subscribe('custom_event', (event: CustomEventPayload) => {
        handleCustomEvent(event, set, get);
      });
    } catch (error) {
      console.error('[WorkflowStore] Connection failed:', error);
      throw error;
    }
  },

  disconnect: () => {
    wsService.disconnect();
    set({ isConnected: false, threadId: null });
  },

  updateStepStatus: (paperTaskId, stepId, status, output) => {
    set(state => {
      const paperTask = state.paperTasks.get(paperTaskId);
      if (!paperTask) return state;

      const updatedSteps = paperTask.steps.map(step =>
        step.id === stepId
          ? {
              ...step,
              status,
              output,
              startTime: status === 'running' && !step.startTime ? new Date() : step.startTime,
              endTime: (status === 'completed' || status === 'error') ? new Date() : undefined,
            }
          : step
      );

      const updatedPaperTask: PaperTaskState = {
        ...paperTask,
        steps: updatedSteps,
        currentStep: stepId,
      };

      state.paperTasks.set(paperTaskId, updatedPaperTask);
      return { paperTasks: new Map(state.paperTasks) };
    });
  },

  addLog: (paperTaskId, stepId, log) => {
    set(state => {
      const paperTask = state.paperTasks.get(paperTaskId);
      if (!paperTask) return state;

      const updatedSteps = paperTask.steps.map(step =>
        step.id === stepId
          ? { ...step, logs: [...(step.logs || []), log] }
          : step
      );

      const updatedPaperTask: PaperTaskState = {
        ...paperTask,
        steps: updatedSteps,
      };

      state.paperTasks.set(paperTaskId, updatedPaperTask);
      return { paperTasks: new Map(state.paperTasks) };
    });
  },

  updateProgress: (paperTaskId, stepId, progress) => {
    set(state => {
      const paperTask = state.paperTasks.get(paperTaskId);
      if (!paperTask) return state;

      const updatedSteps = paperTask.steps.map(step =>
        step.id === stepId ? { ...step, progress } : step
      );

      const updatedPaperTask: PaperTaskState = {
        ...paperTask,
        steps: updatedSteps,
      };

      state.paperTasks.set(paperTaskId, updatedPaperTask);
      return { paperTasks: new Map(state.paperTasks) };
    });
  },

  addMessage: (message) => {
    set(state => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: `msg_${Date.now()}_${Math.random()}`,
          timestamp: new Date(),
        },
      ],
    }));
  },

  setPendingFeedback: (feedback) => {
    set({ pendingFeedback: feedback });
  },

  submitFeedback: (action, payload) => {
    const { threadId, pendingFeedback } = get();
    if (!threadId || !pendingFeedback) {
      console.error('[WorkflowStore] Cannot submit feedback: missing thread or pending feedback');
      return;
    }

    wsService.sendFeedback({
      thread_id: threadId,
      node: 'expert_arbitrator',
      action,
      payload: payload || pendingFeedback.current_value,
    });

    set({ pendingFeedback: null });
  },

  reset: () => {
    set({
      threadId: null,
      requestId: null,
      requestStatus: null,
      paperTasks: new Map(),
      messages: [],
      pendingFeedback: null,
      isStreaming: false,
    });
  },
}));

// Event handlers
function handleStreamEvent(event: StreamEvent, set: any, get: any): void {
  const { metadata, data } = event;
  const nodeId = metadata?.langgraph_node;
  
  if (!nodeId) return;

  const stepId = NODE_TO_STEP_MAP[nodeId as keyof typeof NODE_TO_STEP_MAP];
  if (!stepId) return;

  // Extract paper_task_id from event data
  const paperTaskId = data?.paper_task_id || data?.input?.paper_task_id;
  if (!paperTaskId) {
    console.warn('[WorkflowStore] No paper_task_id in event:', event);
    return;
  }

  switch (event.event) {
    case 'on_chain_start':
      get().updateStepStatus(paperTaskId, stepId, 'running');
      get().addLog(paperTaskId, stepId, `Started ${stepId} processing`);
      break;

    case 'on_chain_end':
      get().updateStepStatus(paperTaskId, stepId, 'completed', data?.output);
      get().addLog(paperTaskId, stepId, `Completed ${stepId}`);
      break;

    case 'on_chain_error':
      get().updateStepStatus(paperTaskId, stepId, 'error');
      get().addLog(paperTaskId, stepId, `Error: ${data?.error || 'Unknown error'}`);
      break;

    case 'on_chat_model_stream':
      // Handle streaming conversation (P0.0)
      if (data?.chunk) {
        get().addMessage({
          role: 'assistant',
          content: data.chunk,
          metadata: { step_id: 'clarification' },
        });
      }
      break;
  }
}

function handleCustomEvent(event: CustomEventPayload, set: any, get: any): void {
  switch (event.type) {
    case 'HUMAN_FEEDBACK_REQUIRED':
      get().setPendingFeedback(event.payload);
      get().updateStepStatus(
        event.payload.paper_task_id,
        'arbitration',
        'waiting_input'
      );
      break;

    case 'PROGRESS_UPDATE':
      get().updateProgress(
        event.payload.paper_task_id,
        event.payload.step,
        event.payload.progress
      );
      if (event.payload.message) {
        get().addLog(
          event.payload.paper_task_id,
          event.payload.step,
          event.payload.message
        );
      }
      break;
  }
}
```

**Step 3: Test store with mock events**

Create `src/stores/workflowStore/index.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useWorkflowStore } from './index';

describe('WorkflowStore', () => {
  beforeEach(() => {
    useWorkflowStore.getState().reset();
  });

  it('should initialize with default state', () => {
    const state = useWorkflowStore.getState();
    expect(state.isConnected).toBe(false);
    expect(state.paperTasks.size).toBe(0);
    expect(state.messages.length).toBe(0);
  });

  it('should update step status correctly', () => {
    const state = useWorkflowStore.getState();
    
    // Create mock paper task
    const paperTaskId = 'paper_123';
    state.paperTasks.set(paperTaskId, {
      paper_task_id: paperTaskId,
      currentStep: 'clarification',
      steps: [
        { id: 'clarification', label: 'Clarification', status: 'pending' },
        { id: 'literature', label: 'Literature', status: 'pending' },
      ],
      status: 'queued',
    });

    // Update status
    state.updateStepStatus(paperTaskId, 'clarification', 'running');
    
    const updatedTask = state.paperTasks.get(paperTaskId);
    expect(updatedTask?.steps[0].status).toBe('running');
    expect(updatedTask?.startTime).toBeDefined();
  });

  it('should add logs to specific step', () => {
    const state = useWorkflowStore.getState();
    const paperTaskId = 'paper_123';
    
    state.paperTasks.set(paperTaskId, {
      paper_task_id: paperTaskId,
      currentStep: 'parsing',
      steps: [
        { id: 'parsing', label: 'Parsing', status: 'running', logs: [] },
      ],
      status: 'running',
    });

    state.addLog(paperTaskId, 'parsing', 'Extracting images...');
    state.addLog(paperTaskId, 'parsing', 'Converting formulas...');

    const task = state.paperTasks.get(paperTaskId);
    expect(task?.steps[0].logs).toHaveLength(2);
    expect(task?.steps[0].logs?.[0]).toBe('Extracting images...');
  });

  it('should handle pending feedback', () => {
    const state = useWorkflowStore.getState();
    
    state.setPendingFeedback({
      paper_task_id: 'paper_123',
      reason: 'PS3 strength uncertain',
      current_value: 'Supporting',
      options: ['Supporting', 'Moderate', 'Strong'],
    });

    expect(state.pendingFeedback).toBeDefined();
    expect(state.pendingFeedback?.reason).toBe('PS3 strength uncertain');
  });
});
```

Run: `npm test -- src/stores/workflowStore/index.test.ts`
Expected: All tests pass

**Step 4: Commit**

```bash
git add src/stores/workflowStore/
git commit -m "feat: add LangGraph-aware workflow state management"
```

---

## Phase 2: Core UI Components

### Task 2.1: Create Workflow Timeline Component

**Files:**
- Create: `src/components/workflow/WorkflowTimeline.tsx`
- Create: `src/components/workflow/WorkflowTimeline.css`

**Step 1: Install rc-steps if not already installed**

```bash
npm install rc-steps
npm install --save-dev @types/rc-steps
```

**Step 2: Create timeline component**

Create `src/components/workflow/WorkflowTimeline.tsx`:

```typescript
import React from 'react';
import Steps from 'rc-steps';
import 'rc-steps/assets/index.css';
import './WorkflowTimeline.css';
import { CheckCircle, Loader2, AlertCircle, Clock, Circle } from 'lucide-react';
import type { WorkflowStep } from '../../stores/workflowStore/types';

interface WorkflowTimelineProps {
  steps: WorkflowStep[];
  currentStepId?: string;
  direction?: 'horizontal' | 'vertical';
  onStepClick?: (stepId: string) => void;
}

const WorkflowTimeline: React.FC<WorkflowTimelineProps> = ({
  steps,
  currentStepId,
  direction = 'horizontal',
  onStepClick,
}) => {
  const getStepIcon = (step: WorkflowStep) => {
    switch (step.status) {
      case 'completed':
        return <CheckCircle className="step-icon step-icon-success" />;
      case 'running':
        return <Loader2 className="step-icon step-icon-running spin" />;
      case 'error':
        return <AlertCircle className="step-icon step-icon-error" />;
      case 'waiting_input':
        return <Clock className="step-icon step-icon-waiting" />;
      case 'pending':
      default:
        return <Circle className="step-icon step-icon-pending" />;
    }
  };

  const getStepStatus = (step: WorkflowStep): 'wait' | 'process' | 'finish' | 'error' => {
    switch (step.status) {
      case 'completed':
        return 'finish';
      case 'running':
      case 'waiting_input':
        return 'process';
      case 'error':
        return 'error';
      case 'pending':
      default:
        return 'wait';
    }
  };

  const getStepDescription = (step: WorkflowStep) => {
    if (step.status === 'error') {
      return <span className="step-error-text">执行失败</span>;
    }

    if (step.status === 'waiting_input') {
      return <span className="step-waiting-text">等待用户输入</span>;
    }

    if (step.progress !== undefined && step.status === 'running') {
      return (
        <div className="step-progress">
          <div className="step-progress-bar">
            <div
              className="step-progress-fill"
              style={{ width: `${step.progress}%` }}
            />
          </div>
          <span className="step-progress-text">{step.progress}%</span>
        </div>
      );
    }

    if (step.status === 'completed' && step.output) {
      // Show output summary based on step type
      if (step.id === 'extraction' && step.output.entities) {
        return <span className="step-output-summary">发现 {step.output.entities.length} 个证据</span>;
      }
      if (step.id === 'classification' && step.output.verdict) {
        return <span className="step-output-summary">初步判定：{step.output.verdict}</span>;
      }
    }

    return step.description || null;
  };

  const currentStepIndex = steps.findIndex(
    s => s.status === 'running' || s.status === 'waiting_input'
  );

  return (
    <div className="workflow-timeline">
      <Steps
        current={currentStepIndex >= 0 ? currentStepIndex : steps.length}
        direction={direction}
        items={steps.map((step) => ({
          title: step.label,
          status: getStepStatus(step),
          icon: getStepIcon(step),
          description: getStepDescription(step),
          className: step.id === currentStepId ? 'step-active' : '',
        }))}
        onChange={(current) => {
          const step = steps[current];
          if (step && onStepClick) {
            onStepClick(step.id);
          }
        }}
      />

      {/* Detailed logs section (collapsible) */}
      {steps.some(s => s.logs && s.logs.length > 0) && (
        <div className="workflow-logs">
          <h3>执行日志</h3>
          {steps
            .filter(s => s.logs && s.logs.length > 0)
            .map(step => (
              <details key={step.id} className="log-section">
                <summary>{step.label} 日志</summary>
                <ul className="log-list">
                  {step.logs?.map((log, i) => (
                    <li key={i} className="log-item">
                      <span className="log-arrow">➜</span> {log}
                    </li>
                  ))}
                </ul>
              </details>
            ))}
        </div>
      )}
    </div>
  );
};

export default WorkflowTimeline;
```

**Step 3: Create CSS styles**

Create `src/components/workflow/WorkflowTimeline.css`:

```css
.workflow-timeline {
  padding: 20px;
  background: var(--color-surface, #ffffff);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* Step icons */
.step-icon {
  width: 24px;
  height: 24px;
}

.step-icon-success {
  color: #10b981; /* green-500 */
}

.step-icon-running {
  color: #3b82f6; /* blue-500 */
}

.step-icon-error {
  color: #ef4444; /* red-500 */
}

.step-icon-waiting {
  color: #f59e0b; /* amber-500 */
}

.step-icon-pending {
  color: #9ca3af; /* gray-400 */
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Step descriptions */
.step-error-text {
  color: #ef4444;
  font-size: 0.875rem;
}

.step-waiting-text {
  color: #f59e0b;
  font-size: 0.875rem;
  font-weight: 500;
}

.step-output-summary {
  color: #059669; /* emerald-600 */
  font-size: 0.875rem;
}

/* Progress bar */
.step-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.step-progress-bar {
  flex: 1;
  height: 6px;
  background: #e5e7eb; /* gray-200 */
  border-radius: 3px;
  overflow: hidden;
}

.step-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  transition: width 0.3s ease;
}

.step-progress-text {
  font-size: 0.75rem;
  color: #6b7280; /* gray-500 */
  min-width: 40px;
  text-align: right;
}

/* Active step highlight */
.step-active {
  background: #eff6ff; /* blue-50 */
  border-radius: 8px;
}

/* Logs section */
.workflow-logs {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.workflow-logs h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 12px;
  color: #111827;
}

.log-section {
  margin-bottom: 16px;
}

.log-section summary {
  cursor: pointer;
  font-weight: 500;
  color: #374151;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 6px;
  user-select: none;
}

.log-section summary:hover {
  background: #f3f4f6;
}

.log-list {
  list-style: none;
  padding: 12px;
  margin: 8px 0 0 0;
  background: #f9fafb;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 0.875rem;
}

.log-item {
  padding: 4px 0;
  color: #4b5563;
}

.log-arrow {
  color: #3b82f6;
  margin-right: 8px;
}
```

**Step 4: Create Storybook/demo usage**

Create `src/components/workflow/WorkflowTimeline.demo.tsx` (for manual testing):

```typescript
import React from 'react';
import WorkflowTimeline from './WorkflowTimeline';
import type { WorkflowStep } from '../../stores/workflowStore/types';

const mockSteps: WorkflowStep[] = [
  {
    id: 'clarification',
    label: '需求澄清 (P0.0)',
    status: 'completed',
    logs: ['用户输入: BRCA1 c.5096G>A', 'Agent 确认: 变异位点已识别'],
  },
  {
    id: 'literature',
    label: '文献获取 (P1.0)',
    status: 'completed',
    output: { pmids: ['12345678', '87654321'] },
    logs: ['从 PubMed 检索到 2 篇相关文献'],
  },
  {
    id: 'parsing',
    label: '文档解析 (P2.0)',
    status: 'running',
    progress: 65,
    logs: ['正在提取图表...', '正在转换公式...'],
  },
  {
    id: 'translation',
    label: '多语言处理 (P3.0)',
    status: 'pending',
  },
  {
    id: 'extraction',
    label: '证据提取 (P4.0)',
    status: 'pending',
  },
  {
    id: 'classification',
    label: 'ACMG 判定 (P5.0)',
    status: 'pending',
  },
  {
    id: 'arbitration',
    label: '专家裁决',
    status: 'pending',
  },
];

export const WorkflowTimelineDemo: React.FC = () => {
  return (
    <div style={{ padding: '40px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1>Workflow Timeline Demo</h1>
      <WorkflowTimeline
        steps={mockSteps}
        currentStepId="parsing"
        direction="horizontal"
        onStepClick={(stepId) => console.log('Clicked step:', stepId)}
      />
    </div>
  );
};

export default WorkflowTimelineDemo;
```

**Step 5: Commit**

```bash
git add src/components/workflow/
git commit -m "feat: add workflow timeline visualization component"
```

---

### Task 2.2: Create Conversational UI Component

**Files:**
- Create: `src/components/conversation/ChatInterface.tsx`
- Create: `src/components/conversation/ChatInterface.css`
- Create: `src/components/conversation/MessageBubble.tsx`

**Step 1: Create message bubble component**

Create `src/components/conversation/MessageBubble.tsx`:

```typescript
import React from 'react';
import { User, Bot, Info } from 'lucide-react';
import type { ConversationMessage } from '../../stores/workflowStore/types';

interface MessageBubbleProps {
  message: ConversationMessage;
  isStreaming?: boolean;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, isStreaming }) => {
  const getIcon = () => {
    switch (message.role) {
      case 'user':
        return <User className="message-icon" />;
      case 'assistant':
        return <Bot className="message-icon" />;
      case 'system':
        return <Info className="message-icon" />;
    }
  };

  const getRoleLabel = () => {
    switch (message.role) {
      case 'user':
        return '您';
      case 'assistant':
        return 'ACMG Agent';
      case 'system':
        return '系统';
    }
  };

  return (
    <div className={`message-bubble message-${message.role}`}>
      <div className="message-header">
        {getIcon()}
        <span className="message-role">{getRoleLabel()}</span>
        <span className="message-time">
          {message.timestamp.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
      <div className="message-content">
        {message.content}
        {isStreaming && <span className="message-cursor">▊</span>}
      </div>
    </div>
  );
};

export default MessageBubble;
```

**Step 2: Create chat interface**

Create `src/components/conversation/ChatInterface.tsx`:

```typescript
import React, { useState, useRef, useEffect } from 'react';
import './ChatInterface.css';
import MessageBubble from './MessageBubble';
import { Send, Upload, Search } from 'lucide-react';
import type { ConversationMessage } from '../../stores/workflowStore/types';

interface ChatInterfaceProps {
  messages: ConversationMessage[];
  onSendMessage: (content: string) => void;
  onUploadPDF?: () => void;
  onSearchPubMed?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  onSendMessage,
  onUploadPDF,
  onSearchPubMed,
  isStreaming = false,
  disabled = false,
  placeholder = '请输入变异信息或上传文献...',
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !disabled && !isStreaming) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="chat-interface">
      {/* Messages area */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty-state">
            <Bot className="empty-state-icon" />
            <h3>开始您的 ACMG 证据分析</h3>
            <p>请告诉我您想要分析的变异信息,或上传相关文献</p>
            
            {/* Quick action buttons */}
            <div className="quick-actions">
              {onUploadPDF && (
                <button
                  type="button"
                  className="quick-action-btn"
                  onClick={onUploadPDF}
                >
                  <Upload size={20} />
                  上传 PDF
                </button>
              )}
              {onSearchPubMed && (
                <button
                  type="button"
                  className="quick-action-btn"
                  onClick={onSearchPubMed}
                >
                  <Search size={20} />
                  检索 PubMed
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                isStreaming={isStreaming && message.id === messages[messages.length - 1]?.id}
              />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input area */}
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || isStreaming}
          rows={1}
          maxLength={2000}
        />
        <button
          type="submit"
          className="chat-send-btn"
          disabled={!input.trim() || disabled || isStreaming}
          title="发送 (Enter)"
        >
          <Send size={20} />
        </button>
      </form>

      {/* Status indicator */}
      {isStreaming && (
        <div className="chat-status">
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span className="status-text">Agent 正在思考...</span>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;
```

**Step 3: Create CSS styles**

Create `src/components/conversation/ChatInterface.css`:

```css
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-background, #f9fafb);
}

/* Messages area */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Empty state */
.chat-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #6b7280;
}

.empty-state-icon {
  width: 64px;
  height: 64px;
  color: #9ca3af;
  margin-bottom: 16px;
}

.chat-empty-state h3 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
  margin-bottom: 8px;
}

.chat-empty-state p {
  font-size: 0.875rem;
  margin-bottom: 24px;
}

.quick-actions {
  display: flex;
  gap: 12px;
}

.quick-action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border: 2px solid #e5e7eb;
  background: white;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-action-btn:hover {
  border-color: #3b82f6;
  color: #3b82f6;
  background: #eff6ff;
}

/* Message bubbles */
.message-bubble {
  display: flex;
  flex-direction: column;
  max-width: 75%;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-user {
  align-self: flex-end;
}

.message-assistant,
.message-system {
  align-self: flex-start;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 0.75rem;
  color: #6b7280;
}

.message-icon {
  width: 16px;
  height: 16px;
}

.message-role {
  font-weight: 500;
}

.message-time {
  margin-left: auto;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.5;
  word-wrap: break-word;
}

.message-user .message-content {
  background: #3b82f6;
  color: white;
  border-bottom-right-radius: 4px;
}

.message-assistant .message-content {
  background: white;
  color: #111827;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 4px;
}

.message-system .message-content {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  font-size: 0.875rem;
}

.message-cursor {
  display: inline-block;
  width: 8px;
  animation: blink 1s infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 49% {
    opacity: 1;
  }
  50%, 100% {
    opacity: 0;
  }
}

/* Input form */
.chat-input-form {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 16px 20px;
  background: white;
  border-top: 1px solid #e5e7eb;
}

.chat-input {
  flex: 1;
  min-height: 44px;
  max-height: 120px;
  padding: 12px 16px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 0.875rem;
  font-family: inherit;
  resize: none;
  transition: border-color 0.2s;
}

.chat-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.chat-input:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
}

.chat-send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.chat-send-btn:hover:not(:disabled) {
  background: #2563eb;
}

.chat-send-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

/* Status indicator */
.chat-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  background: #eff6ff;
  border-top: 1px solid #dbeafe;
  font-size: 0.875rem;
  color: #3b82f6;
}

.typing-indicator {
  display: flex;
  gap: 4px;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: #3b82f6;
  border-radius: 50%;
  animation: bounce 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-8px);
  }
}

.status-text {
  font-weight: 500;
}
```

**Step 4: Commit**

```bash
git add src/components/conversation/
git commit -m "feat: add conversational UI for agent interaction"
```

---

### Task 2.3: Create Human-in-the-Loop Feedback Panel

**Files:**
- Create: `src/components/feedback/ExpertFeedbackPanel.tsx`
- Create: `src/components/feedback/ExpertFeedbackPanel.css`

**Step 1: Create feedback panel component**

Create `src/components/feedback/ExpertFeedbackPanel.tsx`:

```typescript
import React, { useState } from 'react';
import './ExpertFeedbackPanel.css';
import { AlertCircle, CheckCircle, X } from 'lucide-react';

interface ExpertFeedbackPanelProps {
  isOpen: boolean;
  onClose: () => void;
  reason: string;
  currentValue: any;
  options?: any[];
  onConfirm: (value: any) => void;
  onReject: () => void;
  paperTaskId: string;
}

const ExpertFeedbackPanel: React.FC<ExpertFeedbackPanelProps> = ({
  isOpen,
  onClose,
  reason,
  currentValue,
  options,
  onConfirm,
  onReject,
  paperTaskId,
}) => {
  const [selectedValue, setSelectedValue] = useState(currentValue);

  if (!isOpen) return null;

  const handleConfirm = () => {
    onConfirm(selectedValue);
    onClose();
  };

  const handleReject = () => {
    onReject();
    onClose();
  };

  return (
    <div className="feedback-overlay">
      <div className="feedback-panel">
        {/* Header */}
        <div className="feedback-header">
          <div className="feedback-header-content">
            <AlertCircle className="feedback-icon" />
            <h2>专家裁决</h2>
          </div>
          <button
            type="button"
            className="feedback-close-btn"
            onClick={onClose}
            aria-label="关闭"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="feedback-content">
          <div className="feedback-reason">
            <strong>需要您的专业判断：</strong>
            <p>{reason}</p>
          </div>

          <div className="feedback-context">
            <p className="feedback-label">Paper Task ID:</p>
            <code className="feedback-code">{paperTaskId}</code>
          </div>

          <div className="feedback-current-value">
            <p className="feedback-label">系统初步判定：</p>
            <div className="feedback-value-display">
              {typeof currentValue === 'object' ? (
                <pre>{JSON.stringify(currentValue, null, 2)}</pre>
              ) : (
                <span className="feedback-value-text">{currentValue}</span>
              )}
            </div>
          </div>

          {/* Value selector */}
          {options && options.length > 0 ? (
            <div className="feedback-selector">
              <p className="feedback-label">请选择最终判定：</p>
              <div className="feedback-options">
                {options.map((option, index) => (
                  <button
                    key={index}
                    type="button"
                    className={`feedback-option ${selectedValue === option ? 'selected' : ''}`}
                    onClick={() => setSelectedValue(option)}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="feedback-custom-input">
              <p className="feedback-label">请输入您的判定：</p>
              <textarea
                className="feedback-textarea"
                value={selectedValue}
                onChange={(e) => setSelectedValue(e.target.value)}
                rows={4}
                placeholder="输入您的专业意见..."
              />
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="feedback-actions">
          <button
            type="button"
            className="feedback-btn feedback-btn-reject"
            onClick={handleReject}
          >
            <X size={18} />
            拒绝并停止
          </button>
          <button
            type="button"
            className="feedback-btn feedback-btn-confirm"
            onClick={handleConfirm}
            disabled={!selectedValue}
          >
            <CheckCircle size={18} />
            确认并继续
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExpertFeedbackPanel;
```

**Step 2: Create CSS styles**

Create `src/components/feedback/ExpertFeedbackPanel.css`:

```css
.feedback-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.feedback-panel {
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Header */
.feedback-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

.feedback-header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.feedback-icon {
  width: 24px;
  height: 24px;
  color: #f59e0b; /* amber-500 */
}

.feedback-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.feedback-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #6b7280;
  cursor: pointer;
  transition: background 0.2s;
}

.feedback-close-btn:hover {
  background: #f3f4f6;
}

/* Content */
.feedback-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.feedback-reason {
  padding: 16px;
  background: #fef3c7; /* amber-100 */
  border: 1px solid #fde68a;
  border-radius: 8px;
}

.feedback-reason strong {
  display: block;
  margin-bottom: 8px;
  color: #92400e;
  font-size: 0.875rem;
}

.feedback-reason p {
  margin: 0;
  color: #78350f;
  line-height: 1.5;
}

.feedback-context {
  font-size: 0.875rem;
}

.feedback-label {
  margin: 0 0 8px 0;
  font-weight: 500;
  color: #374151;
}

.feedback-code {
  display: block;
  padding: 8px 12px;
  background: #f3f4f6;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 0.875rem;
  color: #1f2937;
}

.feedback-current-value {
  padding: 16px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.feedback-value-display pre {
  margin: 0;
  padding: 12px;
  background: #1f2937;
  color: #f9fafb;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.875rem;
}

.feedback-value-text {
  display: inline-block;
  padding: 6px 12px;
  background: #dbeafe; /* blue-100 */
  color: #1e40af; /* blue-800 */
  border-radius: 6px;
  font-weight: 500;
}

/* Value selector */
.feedback-selector {
  padding: 16px;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
}

.feedback-options {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.feedback-option {
  padding: 10px 20px;
  background: white;
  border: 2px solid #d1d5db;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  transition: all 0.2s;
}

.feedback-option:hover {
  border-color: #3b82f6;
  color: #3b82f6;
}

.feedback-option.selected {
  background: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

/* Custom input */
.feedback-custom-input {
  padding: 16px;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
}

.feedback-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-family: inherit;
  font-size: 0.875rem;
  resize: vertical;
  transition: border-color 0.2s;
}

.feedback-textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Actions */
.feedback-actions {
  display: flex;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid #e5e7eb;
}

.feedback-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.feedback-btn-reject {
  background: #f3f4f6;
  color: #374151;
}

.feedback-btn-reject:hover {
  background: #e5e7eb;
}

.feedback-btn-confirm {
  background: #3b82f6;
  color: white;
}

.feedback-btn-confirm:hover:not(:disabled) {
  background: #2563eb;
}

.feedback-btn-confirm:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
```

**Step 3: Commit**

```bash
git add src/components/feedback/
git commit -m "feat: add human-in-the-loop expert feedback panel"
```

---

## Phase 3: Page Integration

### Task 3.1: Create Agent-Driven Task Creation Page

**Files:**
- Create: `src/pages/tasks/AgentTaskCreatePage.tsx`
- Modify: `src/router/index.tsx`

**Step 1: Create new agent-driven page**

Create `src/pages/tasks/AgentTaskCreatePage.tsx`:

```typescript
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWorkflowStore } from '../../stores/workflowStore';
import ChatInterface from '../../components/conversation/ChatInterface';
import WorkflowTimeline from '../../components/workflow/WorkflowTimeline';
import './AgentTaskCreatePage.css';

const AgentTaskCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const {
    isConnected,
    isStreaming,
    messages,
    paperTasks,
    connect,
    disconnect,
    addMessage,
  } = useWorkflowStore();

  const [isInitializing, setIsInitializing] = useState(true);

  // Connect to WebSocket on mount
  useEffect(() => {
    const initConnection = async () => {
      try {
        await connect();
        
        // Send initial system message
        addMessage({
          role: 'system',
          content: '连接成功！请告诉我您想要分析的变异信息。',
        });
      } catch (error) {
        console.error('Failed to connect:', error);
        addMessage({
          role: 'system',
          content: '连接失败，请刷新页面重试。',
        });
      } finally {
        setIsInitializing(false);
      }
    };

    initConnection();

    return () => {
      disconnect();
    };
  }, []);

  const handleSendMessage = (content: string) => {
    // Add user message to UI
    addMessage({
      role: 'user',
      content,
    });

    // Send to backend via WebSocket
    // Backend will respond with stream events
    // (Implementation depends on backend WebSocket protocol)
  };

  const handleUploadPDF = () => {
    // Navigate to upload page or open file dialog
    console.log('Upload PDF clicked');
  };

  const handleSearchPubMed = () => {
    // Navigate to PubMed search page
    console.log('Search PubMed clicked');
  };

  if (isInitializing) {
    return (
      <div className="agent-task-create-page">
        <div className="loading-container">
          <div className="loading-spinner" />
          <p>正在初始化智能体...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="agent-task-create-page">
      <div className="page-header">
        <h1>ACMG 证据分析</h1>
        <p className="page-subtitle">由智能体引导的交互式分析流程</p>
      </div>

      <div className="page-content">
        {/* Left: Conversation */}
        <div className="conversation-section">
          <ChatInterface
            messages={messages}
            onSendMessage={handleSendMessage}
            onUploadPDF={handleUploadPDF}
            onSearchPubMed={handleSearchPubMed}
            isStreaming={isStreaming}
            disabled={!isConnected}
          />
        </div>

        {/* Right: Workflow visualization */}
        <div className="workflow-section">
          <h2>工作流状态</h2>
          {paperTasks.size > 0 ? (
            <div className="paper-tasks-list">
              {Array.from(paperTasks.values()).map(task => (
                <div key={task.paper_task_id} className="paper-task-card">
                  <div className="paper-task-header">
                    <h3>
                      {task.pmid ? `PMID: ${task.pmid}` : task.filename || 'Unknown'}
                    </h3>
                    <span className={`status-badge status-${task.status}`}>
                      {task.status}
                    </span>
                  </div>
                  <WorkflowTimeline
                    steps={task.steps}
                    currentStepId={task.currentStep}
                    direction="vertical"
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="workflow-empty-state">
              <p>工作流将在您开始对话后显示</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentTaskCreatePage;
```

**Step 2: Create page styles**

Create `src/pages/tasks/AgentTaskCreatePage.css`:

```css
.agent-task-create-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-background, #f9fafb);
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.page-header {
  padding: 24px 32px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
}

.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 1.875rem;
  font-weight: 700;
  color: #111827;
}

.page-subtitle {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
}

.page-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  padding: 24px 32px;
  overflow: hidden;
}

.conversation-section,
.workflow-section {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.workflow-section h2 {
  margin: 0;
  padding: 20px 24px;
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
  border-bottom: 1px solid #e5e7eb;
}

.paper-tasks-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.paper-task-card {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
}

.paper-task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.paper-task-header h3 {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
}

.status-queued {
  background: #f3f4f6;
  color: #6b7280;
}

.status-running {
  background: #dbeafe;
  color: #1e40af;
}

.status-success {
  background: #d1fae5;
  color: #065f46;
}

.status-failed {
  background: #fee2e2;
  color: #991b1b;
}

.workflow-empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 0.875rem;
}

@media (max-width: 1200px) {
  .page-content {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr 1fr;
  }
}
```

**Step 3: Update router**

Modify `src/router/index.tsx`:

```typescript
// Add import
import AgentTaskCreatePage from '../pages/tasks/AgentTaskCreatePage';

// Add route (insert after existing task routes)
{
  path: '/tasks/agent-create',
  element: <AgentTaskCreatePage />,
},
```

**Step 4: Test page**

Run: `npm run dev`
Navigate to: `http://localhost:5173/tasks/agent-create`
Expected: Page renders with chat interface and empty workflow section

**Step 5: Commit**

```bash
git add src/pages/tasks/AgentTaskCreatePage.tsx src/pages/tasks/AgentTaskCreatePage.css src/router/index.tsx
git commit -m "feat: add agent-driven task creation page with real-time workflow"
```

---

## Phase 4: Backend Integration Requirements

### Task 4.1: Document Backend WebSocket Requirements

**Files:**
- Create: `docs/BACKEND_WEBSOCKET_SPEC.md`

**Step 1: Create specification document**

Create `docs/BACKEND_WEBSOCKET_SPEC.md`:

```markdown
# Backend WebSocket Integration Specification

## Overview

This document specifies the WebSocket protocol requirements for the frontend agent-interactive platform. The backend must implement these endpoints and event formats to enable real-time LangGraph streaming.

## WebSocket Endpoint

### Connection

**URL:** `ws://<backend-host>/ws`

**Query Parameters:**
- `thread_id` (optional): Resume existing LangGraph thread

**Authentication:**
- Use JWT token in query parameter or as first message
- Format: `?token=<jwt_token>` or `{"type": "auth", "token": "<jwt_token>"}`

**Connection Lifecycle:**
```
Client -> Server: Connect with optional thread_id
Server -> Client: {"type": "connected", "thread_id": "thread_abc123"}
Client <-> Server: Stream events
Client -> Server: Disconnect
```

## Server-to-Client Events

### 1. Stream Event

Emitted for every LangGraph node execution event.

**Event Name:** `stream_event`

**Payload:**
```typescript
{
  event: 'on_chat_model_stream' | 'on_chain_start' | 'on_chain_end' | 'on_chain_error';
  data?: any;
  metadata?: {
    langgraph_node?: string;        // Node ID (e.g., 'parsing_agent')
    langgraph_checkpoint_id?: string;
    run_id?: string;
    paper_task_id?: string;          // REQUIRED for frontend mapping
  };
  timestamp?: string;
}
```

**Examples:**

```json
// Node start
{
  "event": "on_chain_start",
  "data": {
    "input": {
      "paper_task_id": "paper_12345",
      "pmid": "12345678"
    }
  },
  "metadata": {
    "langgraph_node": "parsing_agent",
    "paper_task_id": "paper_12345"
  },
  "timestamp": "2026-03-07T10:30:00Z"
}

// Node end
{
  "event": "on_chain_end",
  "data": {
    "output": {
      "markdown": "...",
      "images": [...]
    }
  },
  "metadata": {
    "langgraph_node": "parsing_agent",
    "paper_task_id": "paper_12345"
  },
  "timestamp": "2026-03-07T10:30:45Z"
}

// Chat stream (P0.0 clarification)
{
  "event": "on_chat_model_stream",
  "data": {
    "chunk": "收到。检测到变异位点 BRCA1 c.5096G>A。"
  },
  "metadata": {
    "langgraph_node": "clarification_agent"
  },
  "timestamp": "2026-03-07T10:29:30Z"
}
```

### 2. Custom Event

Emitted for business-specific events (progress updates, human feedback requests).

**Event Name:** `custom_event`

**Payload Types:**

#### Human Feedback Required
```typescript
{
  type: 'HUMAN_FEEDBACK_REQUIRED';
  payload: {
    paper_task_id: string;
    reason: string;
    current_value: any;
    options?: any[];  // Predefined choices (e.g., ['Supporting', 'Moderate', 'Strong'])
  };
}
```

**Example:**
```json
{
  "type": "HUMAN_FEEDBACK_REQUIRED",
  "payload": {
    "paper_task_id": "paper_12345",
    "reason": "PS3 强度存疑：实验样本量较小(n=15)，但P值显著(p<0.001)。请专家判断证据强度。",
    "current_value": "Supporting",
    "options": ["Supporting", "Moderate", "Strong"]
  }
}
```

#### Progress Update
```typescript
{
  type: 'PROGRESS_UPDATE';
  payload: {
    paper_task_id: string;
    step: 'parsing' | 'translation' | 'extraction' | 'classification';
    progress: number;  // 0-100
    message?: string;
  };
}
```

**Example:**
```json
{
  "type": "PROGRESS_UPDATE",
  "payload": {
    "paper_task_id": "paper_12345",
    "step": "parsing",
    "progress": 65,
    "message": "正在转换第 13 个公式..."
  }
}
```

## Client-to-Server Events

### 1. Human Feedback

User submits expert arbitration decision.

**Event Name:** `human_feedback`

**Payload:**
```typescript
{
  thread_id: string;
  node: string;           // Always 'expert_arbitrator' for Phase 1
  action: 'confirm' | 'reject' | 'modify';
  payload: any;           // Modified value or original current_value
}
```

**Example:**
```json
{
  "thread_id": "thread_abc123",
  "node": "expert_arbitrator",
  "action": "modify",
  "payload": "Moderate"
}
```

**Backend Response:**
- Resume LangGraph execution from `expert_arbitrator` node
- Continue workflow with updated value
- Emit `on_chain_start` for next node

### 2. User Message

User sends message in P0.0 clarification conversation.

**Event Name:** `user_message`

**Payload:**
```typescript
{
  thread_id: string;
  content: string;
  metadata?: {
    round?: number;  // Clarification round (1 or 2)
  };
}
```

**Example:**
```json
{
  "thread_id": "thread_abc123",
  "content": "请帮我分析 BRCA1 c.5096G>A 的致病性",
  "metadata": {
    "round": 1
  }
}
```

**Backend Response:**
- Pass to `clarification_agent` node
- Stream response via `on_chat_model_stream` events
- Generate task sheet after max 2 rounds

## Error Handling

### Connection Errors

**Event Name:** `error`

**Payload:**
```typescript
{
  code: 'CONNECTION_FAILED' | 'AUTH_FAILED' | 'THREAD_NOT_FOUND';
  message: string;
}
```

### Node Execution Errors

Use `on_chain_error` stream event:
```json
{
  "event": "on_chain_error",
  "data": {
    "error": "MinerU parsing failed: PDF corrupted",
    "traceback": "..."
  },
  "metadata": {
    "langgraph_node": "parsing_agent",
    "paper_task_id": "paper_12345"
  }
}
```

## Implementation Checklist

Backend team must implement:

- [ ] WebSocket endpoint at `/ws`
- [ ] JWT authentication support
- [ ] Thread ID management (create/resume)
- [ ] LangGraph `stream_mode=["updates", "debug", "messages"]`
- [ ] Event emission for all node lifecycle events
- [ ] `paper_task_id` injection in all event metadata
- [ ] Custom event emission for:
  - [ ] `HUMAN_FEEDBACK_REQUIRED` (in `expert_arbitrator` node)
  - [ ] `PROGRESS_UPDATE` (for long-running tasks like parsing)
- [ ] Human feedback reception and workflow resumption
- [ ] Graceful disconnection handling
- [ ] Error event emission

## Testing

Use `wscat` for manual testing:

```bash
npm install -g wscat
wscat -c "ws://localhost:8000/ws?token=<jwt>"

# Send message
> {"type": "user_message", "thread_id": "thread_123", "content": "Hello"}

# Receive stream events
< {"event": "on_chain_start", ...}
```

## References

- [LangGraph Streaming API](https://langchain-ai.github.io/langgraph/concepts/streaming/)
- [Socket.IO Protocol](https://socket.io/docs/v4/server-api/)
- Frontend WebSocket Service: `src/services/websocket.ts`
```

**Step 2: Commit**

```bash
git add docs/BACKEND_WEBSOCKET_SPEC.md
git commit -m "docs: add backend WebSocket integration specification"
```

---

## Phase 5: Advanced Features (Future Work)

### Task 5.1: Knowledge Graph Visualization

**Files:**
- Create: `src/components/graph/KnowledgeGraphViewer.tsx`
- TBD based on Neo4j query workflow requirements

### Task 5.2: Evidence Timeline

**Files:**
- Create: `src/components/evidence/EvidenceTimeline.tsx`
- Show chronological evidence extraction with highlighting

### Task 5.3: Bilingual Side-by-Side Viewer Enhancement

**Files:**
- Modify: `src/pages/DocumentReaderPage.tsx`
- Add real-time entity highlighting synchronized with agent extraction

---

## Summary

This plan transforms the frontend from HTTP polling to a **LangGraph-powered streaming architecture**:

**Implemented:**
- ✅ WebSocket service layer
- ✅ LangGraph-aware state management
- ✅ Workflow timeline visualization
- ✅ Conversational UI for agent interaction
- ✅ Human-in-the-loop feedback panel
- ✅ Agent-driven task creation page
- ✅ Backend WebSocket specification

**Benefits:**
- **Transparency:** Real-time visibility into every agent's processing
- **Interactivity:** Human-in-the-loop for expert arbitration
- **Reliability:** Node-level retry without full workflow restart
- **UX:** Streaming feedback eliminates "loading spinner fatigue"

**Next Steps:**
1. Backend team implements WebSocket endpoint per specification
2. Frontend team integrates with production backend
3. Add knowledge graph visualization (Phase 5)
4. Enhance bilingual viewer with agent-driven highlighting

---

## Execution Options

**Plan complete and saved to `docs/plans/2026-03-07-agent-interactive-platform-refactor.md`.**

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach would you prefer?**
