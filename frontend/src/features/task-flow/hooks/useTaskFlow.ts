"use client";

import { useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTaskFlowStore } from "../stores/taskFlowStore";
import {
  interactionStart,
  interactionRespond,
  confirmTaskForm,
} from "../services/taskFlow";
import type { TaskFormStructured } from "../types/taskFlow";

/**
 * Orchestrates the multi-round agent clarification flow.
 *
 * Wraps the taskFlowStore (local state) with TanStack Query mutations
 * (server communication) so components only call simple methods.
 */
export function useTaskFlow() {
  const store = useTaskFlowStore();

  const startMutation = useMutation({
    mutationFn: (form: TaskFormStructured) => {
      store.setTaskForm(form);
      return interactionStart({ task_form: form });
    },
    onSuccess: (data) => {
      store.setSessionId(data.session_id);
      store.addMessage({
        role: "assistant",
        content: data.message,
      });
      if (!data.is_clarification) {
        store.setClarificationComplete(true);
      }
    },
  });

  const respondMutation = useMutation({
    mutationFn: (answer: string) => {
      if (!store.sessionId) {
        throw new Error("No active session — call startClarification first.");
      }
      store.addMessage({ role: "user", content: answer });
      return interactionRespond({
        session_id: store.sessionId,
        answer,
      });
    },
    onSuccess: (data) => {
      store.addMessage({
        role: "assistant",
        content: data.message,
      });
      store.incrementRound();
      if (!data.is_clarification) {
        store.setClarificationComplete(true);
        if (data.task_form) {
          store.setTaskForm(data.task_form);
        }
      }
    },
  });

  const confirmMutation = useMutation({
    mutationFn: () => {
      if (!store.sessionId) {
        throw new Error("No active session — call startClarification first.");
      }
      return confirmTaskForm(store.sessionId);
    },
    onSuccess: () => {
      store.setConfirmed(true);
    },
  });

  const reset = useCallback(() => {
    store.reset();
  }, [store]);

  return {
    // State from store
    taskForm: store.taskForm,
    messages: store.messages,
    entryMode: store.entryMode,
    sessionId: store.sessionId,
    round: store.round,
    isClarificationComplete: store.isClarificationComplete,
    isConfirmed: store.isConfirmed,

    // Actions
    startClarification: startMutation.mutateAsync,
    respondToAgent: respondMutation.mutateAsync,
    confirmForm: confirmMutation.mutateAsync,
    setEntryMode: store.setEntryMode,
    reset,

    // Loading states
    isStarting: startMutation.isPending,
    isResponding: respondMutation.isPending,
    isConfirming: confirmMutation.isPending,
  };
}
