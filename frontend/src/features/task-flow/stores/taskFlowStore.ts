/**
 * Feature-local Zustand store for the task creation flow.
 *
 * Only used by the task-flow feature module. Not a global store.
 */

import { create } from "zustand";
import type { TaskFormStructured, TaskFlowEntryMode } from "../types/taskFlow";

export interface ChatMessage {
  role: "user" | "assistant" | "system" | "error";
  content: string;
}

interface TaskFlowState {
  taskForm: TaskFormStructured | null;
  messages: ChatMessage[];
  entryMode: TaskFlowEntryMode;
  sessionId: string | null;
  round: number;
  isClarificationComplete: boolean;
  isConfirmed: boolean;

  setTaskForm: (form: TaskFormStructured) => void;
  setEntryMode: (mode: TaskFlowEntryMode) => void;
  setSessionId: (id: string) => void;
  addMessage: (msg: ChatMessage) => void;
  incrementRound: () => void;
  setClarificationComplete: (complete: boolean) => void;
  setConfirmed: (confirmed: boolean) => void;
  reset: () => void;
}

const INITIAL_STATE = {
  taskForm: null,
  messages: [],
  entryMode: "local" as TaskFlowEntryMode,
  sessionId: null,
  round: 0,
  isClarificationComplete: false,
  isConfirmed: false,
};

export const useTaskFlowStore = create<TaskFlowState>((set) => ({
  ...INITIAL_STATE,

  setTaskForm: (form) => set({ taskForm: form }),
  setEntryMode: (mode) => set({ entryMode: mode }),
  setSessionId: (id) => set({ sessionId: id }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  incrementRound: () => set((s) => ({ round: s.round + 1 })),
  setClarificationComplete: (complete) =>
    set({ isClarificationComplete: complete }),
  setConfirmed: (confirmed) => set({ isConfirmed: confirmed }),
  reset: () => set(INITIAL_STATE),
}));
