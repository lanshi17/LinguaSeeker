import { Avatar } from "antd";
import { User } from "lucide-react";
import type { ChatAction, ChatActionIntent } from "../types/actions";

/** Max words of the first user message used as the session title. */
export const SESSION_TITLE_WORDS = 5;

/** localStorage key for the task-queue panel visibility preference. */
export const TASK_QUEUE_STORAGE_KEY = "chat.taskQueueOpen";

export function readInitialQueueOpen(): boolean {
  if (typeof window === "undefined") return true;
  const stored = window.localStorage.getItem(TASK_QUEUE_STORAGE_KEY);
  return stored === null ? true : stored === "1";
}

export interface ChatViewProps {
  processingRunId?: string;
  sessionId?: string;
}

// ─── Role config for Bubble.List ───────────────────────────────────────

export const roles = {
  assistant: {
    placement: "start" as const,
    avatar: (
      <Avatar src="/images/chatbot.png" style={{ backgroundColor: "var(--color-primary-600, var(--color-primary-600))" }} />
    ),
  },
  user: {
    placement: "end" as const,
    avatar: (
      <Avatar icon={<User style={{ fontSize: 18 }} />} style={{ backgroundColor: "var(--color-success-500, var(--color-success-500))" }} />
    ),
  },
};

// ─── Per-session ephemeral UI state shape ──────────────────────────────

export interface PerSessionUIState {
  activeForm: ChatActionIntent | null;
  activeFormSlots: ChatAction["slots"] | null;
  dispatchedActions: Set<string>;
  pipelineStatus: {
    runId: string;
    status: string;
    phases?: Record<
      string,
      { status: string; duration_seconds?: number | null }
    >;
  } | null;
}

/** Returns a fresh default state object. Uses a factory (not a constant)
 *  so that `dispatchedActions` is never shared across sessions. */
export function createEmptySessionUI(): PerSessionUIState {
  return {
    activeForm: null,
    activeFormSlots: null,
    dispatchedActions: new Set<string>(),
    pipelineStatus: null,
  };
}
