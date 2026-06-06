"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { TaskForm } from "./TaskForm";
import { ClarificationChat } from "./ClarificationChat";
import { TaskConfirmPanel } from "./TaskConfirmPanel";
import { useTaskFlow } from "../hooks/useTaskFlow";
import { useToastStore } from "@/stores/toastStore";
import type { TaskFormStructured } from "../types/taskFlow";

const EMPTY_FORM: TaskFormStructured = {
  goal: "",
  disease: "",
  country: "",
  language: "",
  pmid: "",
};

/** Client wrapper for the agent task creation flow. */
export function TaskCreateView() {
  const {
    startClarification,
    respondToAgent,
    confirmForm,
    messages,
    taskForm,
    isClarificationComplete,
    isConfirmed,
    isStarting,
    isResponding,
    isConfirming,
  } = useTaskFlow();

  const addToast = useToastStore((s) => s.addToast);
  const [form, setForm] = useState<TaskFormStructured>(EMPTY_FORM);

  async function handleStart() {
    if (!form.goal || !form.disease) {
      addToast({
        level: "warning",
        title: "Missing fields",
        message: "Goal and Disease are required.",
      });
      return;
    }
    try {
      await startClarification(form);
    } catch {
      addToast({ level: "error", title: "Failed to start clarification" });
    }
  }

  async function handleSend(answer: string) {
    try {
      await respondToAgent(answer);
    } catch {
      addToast({ level: "error", title: "Failed to send response" });
    }
  }

  async function handleConfirm() {
    try {
      await confirmForm();
      addToast({ level: "success", title: "Task form confirmed" });
    } catch {
      addToast({ level: "error", title: "Failed to confirm" });
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBoundary>
        <Card>
          <h3 className="mb-4 text-sm font-semibold text-gray-700">
            Task Parameters
          </h3>
          <TaskForm value={form} onChange={setForm} disabled={isStarting} />
          <Button
            className="mt-4"
            onClick={handleStart}
            loading={isStarting}
            disabled={!form.goal || !form.disease}
          >
            Start Clarification
          </Button>
        </Card>
      </ErrorBoundary>

      {messages.length > 0 && (
        <ErrorBoundary>
          <ClarificationChat
            messages={messages}
            onSend={handleSend}
            isSending={isResponding}
            disabled={isClarificationComplete}
          />
        </ErrorBoundary>
      )}

      {isClarificationComplete && (
        <ErrorBoundary>
          <TaskConfirmPanel
            taskForm={taskForm}
            onConfirm={handleConfirm}
            isConfirming={isConfirming}
            isConfirmed={isConfirmed}
          />
        </ErrorBoundary>
      )}
    </div>
  );
}
