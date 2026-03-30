import { create } from 'zustand';

import type { TaskFormStructured } from '../types/api';
import type { ChatMessage } from '../types/chat';

export type TaskEntryMode = 'documents' | 'graph' | null;

type TaskFlowState = {
  taskForm: TaskFormStructured | null;
  interactionSessionId: string | null;
  interactionRound: number;
  entryMode: TaskEntryMode;
  confirmedRequestId: string | null;
  taskFormPayload: Record<string, unknown> | null;
  interactionMessages: ChatMessage[];
  setTaskForm: (taskForm: TaskFormStructured | null) => void;
  setInteraction: (sessionId: string | null, round: number) => void;
  setEntryMode: (entryMode: TaskEntryMode) => void;
  setConfirmedRequestId: (requestId: string | null) => void;
  setTaskFormPayload: (payload: Record<string, unknown> | null) => void;
  setInteractionMessages: (messages: ChatMessage[]) => void;
  appendInteractionMessage: (message: ChatMessage) => void;
  clearInteractionMessages: () => void;
};

export const useTaskFlowStore = create<TaskFlowState>((set) => ({
  taskForm: null,
  interactionSessionId: null,
  interactionRound: 0,
  entryMode: null,
  confirmedRequestId: null,
  taskFormPayload: null,
  interactionMessages: [],
  setTaskForm: (taskForm) => set({ taskForm }),
  setInteraction: (interactionSessionId, interactionRound) => set({ interactionSessionId, interactionRound }),
  setEntryMode: (entryMode) => set({ entryMode }),
  setConfirmedRequestId: (confirmedRequestId) => set({ confirmedRequestId }),
  setTaskFormPayload: (taskFormPayload) => set({ taskFormPayload }),
  setInteractionMessages: (interactionMessages) => set({ interactionMessages }),
  appendInteractionMessage: (message) => set((state) => ({ interactionMessages: [...state.interactionMessages, message] })),
  clearInteractionMessages: () => set({ interactionMessages: [] })
}));
