import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Save, X } from "lucide-react";
import { App, Button, Select } from "antd";
import { patchEvidence } from "../services/evidenceCorrection";
import type { ReviewStatusValue } from "@/lib/types/evidence";
import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();
  const STATUS_OPTIONS: { label: string; value: ReviewStatusValue }[] = [
    { label: t("evidence.correct.status.approved"), value: "approved" },
    { label: t("evidence.correct.status.corrected"), value: "corrected" },
    { label: t("evidence.correct.status.rejected"), value: "rejected" },
  ];

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
        backgroundColor: "var(--color-highlight)",
        padding: "16px 20px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h4 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
          {t("evidence.correct.heading")}
        </h4>
        <button
          type="button"
          onClick={onClose}
          style={{
            borderRadius: 4,
            padding: 4,
            color: "var(--color-text-muted)",
            border: "none",
            background: "none",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "var(--color-bg-muted)";
            e.currentTarget.style.color = "var(--color-text-strong)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "transparent";
            e.currentTarget.style.color = "var(--color-text-muted)";
          }}
        >
          <X style={{ width: 16, height: 16 }} />
        </button>
      </div>

      {cardField && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--color-text-strong)" }}>
            {t("evidence.correct.value")} ({cardField})
          </label>
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            rows={2}
            style={{
              width: "100%",
              borderRadius: 8,
              border: `1px solid ${valueChanged ? "var(--color-highlight-amber-border)" : "var(--color-border)"}`,
              backgroundColor: valueChanged ? "var(--color-highlight-amber)" : "var(--color-surface)",
              padding: "8px 12px",
              fontSize: 14,
              color: "var(--color-text)",
              transition: "border-color 150ms, box-shadow 150ms",
              outline: "none",
              boxSizing: "border-box",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--color-primary-400)";
              e.currentTarget.style.boxShadow = "0 0 0 2px var(--color-primary-200)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = valueChanged ? "var(--color-highlight-amber-border)" : "var(--color-border)";
              e.currentTarget.style.boxShadow = "none";
            }}
            placeholder={t("evidence.correct.valuePh")}
          />
          {valueChanged && (
            <p style={{ fontSize: 11, color: "var(--color-warning-text)", margin: 0 }}>{t("evidence.correct.valueChanged")}</p>
          )}
        </div>
      )}

      <div style={{ marginTop: 12, display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>
            {t("evidence.correct.reviewStatus")}
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
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--color-text-strong)" }}>
            {t("evidence.correct.reason")}
          </label>
          <input
            type="text"
            value={changeReason}
            onChange={(e) => setChangeReason(e.target.value)}
            placeholder={t("evidence.correct.reasonPh")}
            style={{
              width: "100%",
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              padding: "8px 12px",
              fontSize: 14,
              color: "var(--color-text)",
              transition: "border-color 150ms, box-shadow 150ms",
              outline: "none",
              boxSizing: "border-box",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--color-primary-400)";
              e.currentTarget.style.boxShadow = "0 0 0 2px var(--color-primary-200)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--color-border)";
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
          {t("evidence.correct.save")}
        </Button>

        <div style={{ display: "flex", alignItems: "center", gap: 6, borderLeft: "1px solid var(--color-border)", paddingLeft: 8 }}>
          <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{t("evidence.correct.quick")}</span>
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
                backgroundColor: "var(--color-highlight-green)",
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 500,
                color: "var(--color-success-text)",
                border: "none",
                cursor: isSubmitting ? "not-allowed" : "pointer",
                opacity: isSubmitting ? 0.5 : 1,
                transition: "background-color 150ms",
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.backgroundColor = "var(--color-success-100)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "var(--color-highlight-green)";
              }}
            >
              <CheckCircle2 style={{ width: 12, height: 12 }} />
              {t("evidence.correct.approve")}
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
                backgroundColor: "var(--color-error-bg)",
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 500,
                color: "var(--color-error-text)",
                border: "none",
                cursor: isSubmitting ? "not-allowed" : "pointer",
                opacity: isSubmitting ? 0.5 : 1,
                transition: "background-color 150ms",
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.backgroundColor = "var(--color-error-bg)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "var(--color-error-bg)";
              }}
            >
              <X style={{ width: 12, height: 12 }} />
              {t("evidence.correct.reject")}
            </button>
          )}
        </div>
      </div>

      <p style={{ marginTop: 8, fontSize: 10, color: "var(--color-text-muted)" }}>
        {t("evidence.correct.footer", { field: fieldId, status: currentStatus })}
      </p>
    </form>
  );
}
