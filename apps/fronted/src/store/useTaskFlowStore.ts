import { create } from 'zustand';

import type { TaskFormStructured } from '../types/api';

export type TaskEntryMode = 'documents' | 'graph' | null;

type TaskFlowState = {
  taskForm: TaskFormStructured | null;
  interactionSessionId: string | null;
  interactionRound: number;
  entryMode: TaskEntryMode;
  setTaskForm: (taskForm: TaskFormStructured | null) => void;
  setInteraction: (sessionId: string | null, round: number) => void;
  setEntryMode: (entryMode: TaskEntryMode) => void;
};

export const useTaskFlowStore = create<TaskFlowState>((set) => ({
  taskForm: null,
  interactionSessionId: null,
  interactionRound: 0,
  entryMode: null,
  setTaskForm: (taskForm) => set({ taskForm }),
  setInteraction: (interactionSessionId, interactionRound) => set({ interactionSessionId, interactionRound }),
  setEntryMode: (entryMode) => set({ entryMode })
}));
