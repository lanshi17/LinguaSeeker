"use client";

import { Input } from "@/components/ui/Input";
import type { TaskFormStructured } from "../types/taskFlow";

interface TaskFormProps {
  value: TaskFormStructured;
  onChange: (form: TaskFormStructured) => void;
  disabled?: boolean;
}

export function TaskForm({ value, onChange, disabled }: TaskFormProps) {
  function update(field: keyof TaskFormStructured, val: string) {
    onChange({ ...value, [field]: val });
  }

  return (
    <div className="space-y-4">
      <Input
        label="Research Goal"
        placeholder="e.g., Classify ACMG evidence for BRCA1 variant"
        value={value.goal}
        onChange={(e) => update("goal", e.target.value)}
        disabled={disabled}
        required
      />
      <Input
        label="Disease"
        placeholder="e.g., Breast cancer"
        value={value.disease}
        onChange={(e) => update("disease", e.target.value)}
        disabled={disabled}
        required
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Country (optional)"
          placeholder="e.g., China"
          value={value.country ?? ""}
          onChange={(e) => update("country", e.target.value)}
          disabled={disabled}
        />
        <Input
          label="Language (optional)"
          placeholder="e.g., Chinese"
          value={value.language ?? ""}
          onChange={(e) => update("language", e.target.value)}
          disabled={disabled}
        />
      </div>
      <Input
        label="PMID (optional)"
        placeholder="e.g., 12345678"
        value={value.pmid ?? ""}
        onChange={(e) => update("pmid", e.target.value)}
        disabled={disabled}
      />
    </div>
  );
}
