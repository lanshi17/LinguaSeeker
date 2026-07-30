import { Avatar } from "antd";
import { User } from "lucide-react";
import type { KnowledgeGraph } from "@/features/graphrag";
import type { ChatAction, ChatActionIntent } from "../types/actions";

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
      <Avatar src="https://acmg-bucket.oss-cn-shenzhen.aliyuncs.com/chatbot.jpg" style={{ backgroundColor: "var(--color-primary-600, var(--color-primary-600))" }} />
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
  activeUploadFile: File | null;
  dispatchedActions: Set<string>;
  pipelineStatus: {
    runId: string;
    status: string;
    phases?: Record<
      string,
      { status: string; duration_seconds?: number | null }
    >;
  } | null;
  /** Inline knowledge-graph Q&A result, auto-dispatched from a graph-qa action. */
  graphResult: {
    dispatchKey: string;
    question: string;
    status: "loading" | "done" | "error";
    answer?: string;
    subgraph?: KnowledgeGraph;
    error?: string;
  } | null;
}

/** Returns a fresh default state object. Uses a factory (not a constant)
 *  so that `dispatchedActions` is never shared across sessions. */
export function createEmptySessionUI(): PerSessionUIState {
  return {
    activeForm: null,
    activeFormSlots: null,
    activeUploadFile: null,
    dispatchedActions: new Set<string>(),
    pipelineStatus: null,
    graphResult: null,
  };
}
