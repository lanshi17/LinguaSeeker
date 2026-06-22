import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Save, X } from "lucide-react";
import { App, Button, Select } from "antd";
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
  const { message } = App.useApp();

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

        message.success(
          `Evidence updated: ${result.deltas} field(s) changed: ${result.old_status} → ${result.new_status}`,
        );
        onClose();
      } catch (err) {
        message.error(err instanceof Error ? err.message : "Failed to update evidence");
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      message,
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
        message.success(`Evidence ${status}`);
        onClose();
      } catch (err) {
        message.error(err instanceof Error ? err.message : "Failed to update status");
      } finally {
        setIsSubmitting(false);
      }
    },
    [message, canonicalEvidenceId, groupId, isSubmitting, onClose, queryClient],
  );

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        borderTop: "1px solid var(--color-primary-100)",
        backgroundColor: "rgba(236, 254, 255, 0.3)",
        padding: "16px 20px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h4 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
          Correct evidence
        </h4>
        <button
          type="button"
          onClick={onClose}
          style={{
            borderRadius: 4,
            padding: 4,
            color: "#9ca3af",
            border: "none",
            background: "none",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "#f3f4f6";
            e.currentTarget.style.color = "#4b5563";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "transparent";
            e.currentTarget.style.color = "#9ca3af";
          }}
        >
          <X style={{ width: 16, height: 16 }} />
        </button>
      </div>

      {cardField && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "#4b5563" }}>
            Value ({cardField})
          </label>
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            rows={2}
            style={{
              width: "100%",
              borderRadius: 8,
              border: `1px solid ${valueChanged ? "#fcd34d" : "#e5e7eb"}`,
              backgroundColor: valueChanged ? "#fffbeb" : "#fff",
              padding: "8px 12px",
              fontSize: 14,
              color: "#111827",
              transition: "border-color 150ms, box-shadow 150ms",
              outline: "none",
              boxSizing: "border-box",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--color-primary-400)";
              e.currentTarget.style.boxShadow = "0 0 0 2px var(--color-primary-200)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = valueChanged ? "#fcd34d" : "#e5e7eb";
              e.currentTarget.style.boxShadow = "none";
            }}
            placeholder="Enter corrected value..."
          />
          {valueChanged && (
            <p style={{ fontSize: 11, color: "#d97706", margin: 0 }}>Value changed</p>
          )}
        </div>
      )}

      <div style={{ marginTop: 12, display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "rgba(0,0,0,0.88)" }}>
            Review status
          </label>
          <Select
            value={newStatus}
            onChange={(val) =>
              setNewStatus(val as ReviewStatusValue)
            }
            options={STATUS_OPTIONS}
            style={{ width: "100%" }}
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "#4b5563" }}>
            Reason (optional)
          </label>
          <input
            type="text"
            value={changeReason}
            onChange={(e) => setChangeReason(e.target.value)}
            placeholder="Why this change?"
            style={{
              width: "100%",
              borderRadius: 8,
              border: "1px solid #e5e7eb",
              backgroundColor: "#fff",
              padding: "8px 12px",
              fontSize: 14,
              color: "#111827",
              transition: "border-color 150ms, box-shadow 150ms",
              outline: "none",
              boxSizing: "border-box",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--color-primary-400)";
              e.currentTarget.style.boxShadow = "0 0 0 2px var(--color-primary-200)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#e5e7eb";
              e.currentTarget.style.boxShadow = "none";
            }}
          />
        </div>
      </div>

      <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <Button
          htmlType="submit"
          size="small"
          disabled={!hasChanges || isSubmitting}
          loading={isSubmitting}
        >
          <Save style={{ width: 14, height: 14, marginRight: 6 }} />
          Save correction
        </Button>

        <div style={{ display: "flex", alignItems: "center", gap: 6, borderLeft: "1px solid #e5e7eb", paddingLeft: 8 }}>
          <span style={{ fontSize: 11, color: "#6b7280" }}>Quick:</span>
          {currentStatus !== "approved" && (
            <button
              type="button"
              onClick={() => handleQuickStatus("approved")}
              disabled={isSubmitting}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                borderRadius: 6,
                backgroundColor: "#ecfdf5",
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 500,
                color: "#047857",
                border: "none",
                cursor: isSubmitting ? "not-allowed" : "pointer",
                opacity: isSubmitting ? 0.5 : 1,
                transition: "background-color 150ms",
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.backgroundColor = "#d1fae5";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "#ecfdf5";
              }}
            >
              <CheckCircle2 style={{ width: 12, height: 12 }} />
              Approve
            </button>
          )}
          {currentStatus !== "rejected" && (
            <button
              type="button"
              onClick={() => handleQuickStatus("rejected")}
              disabled={isSubmitting}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                borderRadius: 6,
                backgroundColor: "#fef2f2",
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 500,
                color: "#b91c1c",
                border: "none",
                cursor: isSubmitting ? "not-allowed" : "pointer",
                opacity: isSubmitting ? 0.5 : 1,
                transition: "background-color 150ms",
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.backgroundColor = "#fee2e2";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "#fef2f2";
              }}
            >
              <X style={{ width: 12, height: 12 }} />
              Reject
            </button>
          )}
        </div>
      </div>

      <p style={{ marginTop: 8, fontSize: 10, color: "#9ca3af" }}>
        Field: <code style={{ borderRadius: 4, backgroundColor: "#f3f4f6", padding: "0 4px" }}>{fieldId}</code> ·
        Current status: <span style={{ fontWeight: 500 }}>{currentStatus}</span>
      </p>
    </form>
  );
}
