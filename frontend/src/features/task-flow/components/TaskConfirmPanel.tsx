"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { TaskFormStructured } from "../types/taskFlow";

interface TaskConfirmPanelProps {
  taskForm: TaskFormStructured | null;
  onConfirm: () => void;
  isConfirming: boolean;
  isConfirmed: boolean;
}

export function TaskConfirmPanel({
  taskForm,
  onConfirm,
  isConfirming,
  isConfirmed,
}: TaskConfirmPanelProps) {
  if (!taskForm) return null;

  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-gray-700">
        Confirm Task Form
      </h3>

      <dl className="space-y-2 text-sm">
        <div>
          <dt className="inline font-medium text-gray-500">Goal: </dt>
          <dd className="inline text-gray-900">{taskForm.goal}</dd>
        </div>
        <div>
          <dt className="inline font-medium text-gray-500">Disease: </dt>
          <dd className="inline text-gray-900">{taskForm.disease}</dd>
        </div>
        {taskForm.country && (
          <div>
            <dt className="inline font-medium text-gray-500">Country: </dt>
            <dd className="inline text-gray-900">{taskForm.country}</dd>
          </div>
        )}
        {taskForm.language && (
          <div>
            <dt className="inline font-medium text-gray-500">Language: </dt>
            <dd className="inline text-gray-900">{taskForm.language}</dd>
          </div>
        )}
      </dl>

      {!isConfirmed && (
        <Button
          className="mt-4"
          onClick={onConfirm}
          loading={isConfirming}
        >
          Confirm Task Form
        </Button>
      )}

      {isConfirmed && (
        <p className="mt-4 text-sm font-medium text-green-700">
          Task form confirmed.
        </p>
      )}
    </Card>
  );
}
