import { create } from 'zustand';

import type { TaskFormStructured } from '../types/api';

type TaskFlowState = {
  taskForm: TaskFormStructured | null;
  interactionSessionId: string | null;
  interactionRound: number;
  setTaskForm: (taskForm: TaskFormStructured | null) => void;
  setInteraction: (sessionId: string | null, round: number) => void;
};

export const useTaskFlowStore = create<TaskFlowState>((set) => ({
  taskForm: null,
  interactionSessionId: null,
  interactionRound: 0,
  setTaskForm: (taskForm) => set({ taskForm }),
  setInteraction: (interactionSessionId, interactionRound) => set({ interactionSessionId, interactionRound })
}));
