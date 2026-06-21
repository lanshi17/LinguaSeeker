import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Save, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { useToastStore } from "@/stores/toastStore";
import { cn } from "@/lib/utils/cn";
import { patchEvidence } from "../services/evidenceCorrection";
import type { ReviewStatusValue } from "../types/evidenceSearch";

interface EvidenceCorrectionFormProps {
  canonicalEvidenceId: string;
  currentValue: string | null;
  currentStatus: string;
  fieldId: string;
  /** The card-level field name (e.g. "gene", "variant") for patching. */
  cardField: string | null;
  groupId: string;
  onClose: () => void;
}

const STATUS_OPTIONS: { label: string; value: ReviewStatusValue }[] = [
  { label: "Approved", value: "approved" },
  { label: "Corrected", value: "corrected" },
  { label: "Rejected", value: "rejected" },
];

export function EvidenceCorrectionForm({
  canonicalEvidenceId,
  currentValue,
  currentStatus,
  fieldId,
  cardField,
  groupId,
  onClose,
}: EvidenceCorrectionFormProps) {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  const [editValue, setEditValue] = useState(currentValue ?? "");
  const [newStatus, setNewStatus] = useState<ReviewStatusValue>("corrected");
  const [changeReason, setChangeReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const valueChanged = editValue !== (currentValue ?? "");
  const statusChanged = newStatus !== currentStatus;
  const hasChanges = valueChanged || statusChanged;

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!hasChanges || isSubmitting) return;

      setIsSubmitting(true);
      try {
        const fields: Record<string, string> = {};
        if (valueChanged && cardField) {
          fields[cardField] = editValue;
        }

        const result = await patchEvidence(canonicalEvidenceId, {
          fields,
          change_reason: changeReason.trim() || undefined,
          new_status: statusChanged ? newStatus : undefined,
        });

        queryClient.invalidateQueries({
          queryKey: ["evidence", "group", groupId],
        });

        addToast({
          level: "success",
          title: "Evidence updated",
          message: `${result.deltas} field(s) changed: ${result.old_status} → ${result.new_status}`,
        });
        onClose();
      } catch (err) {
        addToast({
          level: "error",
          title: "Failed to update evidence",
          message: err instanceof Error ? err.message : "Unknown error",
        });
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      addToast,
      canonicalEvidenceId,
      cardField,
      changeReason,
      editValue,
      groupId,
      hasChanges,
      isSubmitting,
      newStatus,
      onClose,
      queryClient,
      statusChanged,
      valueChanged,
    ],
  );

  const handleQuickStatus = useCallback(
    async (status: ReviewStatusValue) => {
      if (isSubmitting) return;
      setIsSubmitting(true);
      try {
        await patchEvidence(canonicalEvidenceId, {
          fields: {},
          new_status: status,
        });
        queryClient.invalidateQueries({
          queryKey: ["evidence", "group", groupId],
        });
        addToast({
          level: "success",
          title: `Evidence ${status}`,
        });
        onClose();
      } catch (err) {
        addToast({
          level: "error",
          title: "Failed to update status",
          message: err instanceof Error ? err.message : "Unknown error",
        });
      } finally {
        setIsSubmitting(false);
      }
    },
    [addToast, canonicalEvidenceId, groupId, isSubmitting, onClose, queryClient],
  );

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-primary-100 bg-primary-50/30 px-5 py-4"
    >
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-gray-900">
          Correct evidence
        </h4>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {cardField && (
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-gray-600">
            Value ({cardField})
          </label>
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            rows={2}
            className={cn(
              "w-full rounded-lg border px-3 py-2 text-sm text-gray-900 transition-colors",
              "focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200",
              valueChanged
                ? "border-amber-300 bg-amber-50"
                : "border-gray-200 bg-white",
            )}
            placeholder="Enter corrected value..."
          />
          {valueChanged && (
            <p className="text-[11px] text-amber-600">Value changed</p>
          )}
        </div>
      )}

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Select
          label="Review status"
          value={newStatus}
          onChange={(e) =>
            setNewStatus(e.target.value as ReviewStatusValue)
          }
          options={STATUS_OPTIONS}
        />
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-gray-600">
            Reason (optional)
          </label>
          <input
            type="text"
            value={changeReason}
            onChange={(e) => setChangeReason(e.target.value)}
            placeholder="Why this change?"
            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 transition-colors focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          type="submit"
          size="sm"
          disabled={!hasChanges || isSubmitting}
          loading={isSubmitting}
        >
          <Save className="mr-1.5 h-3.5 w-3.5" />
          Save correction
        </Button>

        <div className="flex items-center gap-1.5 border-l border-gray-200 pl-2">
          <span className="text-[11px] text-gray-500">Quick:</span>
          {currentStatus !== "approved" && (
            <button
              type="button"
              onClick={() => handleQuickStatus("approved")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 transition-colors hover:bg-emerald-100 disabled:opacity-50"
            >
              <CheckCircle2 className="h-3 w-3" />
              Approve
            </button>
          )}
          {currentStatus !== "rejected" && (
            <button
              type="button"
              onClick={() => handleQuickStatus("rejected")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1 rounded-md bg-red-50 px-2.5 py-1 text-[11px] font-medium text-red-700 transition-colors hover:bg-red-100 disabled:opacity-50"
            >
              <X className="h-3 w-3" />
              Reject
            </button>
          )}
        </div>
      </div>

      <p className="mt-2 text-[10px] text-gray-400">
        Field: <code className="rounded bg-gray-100 px-1">{fieldId}</code> ·
        Current status: <span className="font-medium">{currentStatus}</span>
      </p>
    </form>
  );
}
