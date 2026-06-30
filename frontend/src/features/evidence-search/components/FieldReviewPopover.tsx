/**
 * Popover that appears on hover/click of an evidence highlight <mark>.
 * Shows field info + quick review actions (approve / correct / reject).
 */
import { useCallback, useState } from "react";
import { App, Popover, Button } from "antd";
import { Badge } from "@/components/ui/Badge";
import { CheckCircle2, XCircle, Pencil } from "lucide-react";
import { patchEvidence } from "../services/evidenceCorrection";
import type { ReviewStatusValue } from "@/lib/types/evidence";
import { useI18n } from "@/lib/i18n";

export interface FieldReviewInfo {
  /** canonical_evidence_id of the highlighted evidence item. */
  evidenceId: string;
  /** field_id (e.g. "A.classification"). */
  fieldId: string;
  /** Human-readable field name. */
  label: string;
  /** Category letter (A–J). */
  category?: string | null;
  /** Current review status of the evidence item. */
  currentStatus: string;
  /** Current value text. */
  value?: string | null;
  /** group_id for cache invalidation. */
  groupId: string;
}

interface FieldReviewPopoverProps {
  info: FieldReviewInfo;
  children: React.ReactElement;
  /** Called after a successful review action to refresh parent data. */
  onReviewed?: () => void;
}

const QUICK_ACTIONS: { status: ReviewStatusValue; icon: typeof CheckCircle2; tone: string }[] = [
  { status: "approved", icon: CheckCircle2, tone: "var(--color-success-text, #16a34a)" },
  { status: "corrected", icon: Pencil, tone: "var(--color-warning-text, #d97706)" },
  { status: "rejected", icon: XCircle, tone: "var(--color-error-text, #dc2626)" },
];

export function FieldReviewPopover({ info, children, onReviewed }: FieldReviewPopoverProps) {
  const { t } = useI18n();
  const { message } = App.useApp();
  const [submitting, setSubmitting] = useState<ReviewStatusValue | null>(null);

  const handleReview = useCallback(
    async (status: ReviewStatusValue) => {
      setSubmitting(status);
      try {
        await patchEvidence(info.evidenceId, { fields: {}, new_status: status });
        message.success(t("evidence.review.success", { status }));
        onReviewed?.();
      } catch {
        message.error(t("evidence.review.error"));
      } finally {
        setSubmitting(null);
      }
    },
    [info.evidenceId, message, onReviewed, t],
  );

  const statusBadge: Record<string, "default" | "success" | "warning" | "error"> = {
    provisional: "default",
    approved: "success",
    corrected: "warning",
    rejected: "error",
  };

  return (
    <Popover
      trigger="hover"
      mouseEnterDelay={0.3}
      mouseLeaveDelay={0.15}
      placement="top"
      arrow={{ pointAtCenter: true }}
      overlayInnerStyle={{ padding: 0, minWidth: 220 }}
      content={
        <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-strong)" }}>
              {info.label}
            </span>
            <Badge
              variant={statusBadge[info.currentStatus] ?? "default"}
              style={{ fontSize: 10 }}
            >
              {info.currentStatus}
            </Badge>
          </div>

          {/* Field ID + value */}
          <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
            {info.fieldId}
          </span>
          {info.value && (
            <p
              style={{
                fontSize: 12,
                lineHeight: "18px",
                color: "var(--color-text-secondary)",
                margin: 0,
                maxHeight: 54,
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {info.value}
            </p>
          )}

          {/* Quick action buttons — skip the current status */}
          <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
            {QUICK_ACTIONS.filter((a) => a.status !== info.currentStatus).map((action) => (
              <Button
                key={action.status}
                size="small"
                loading={submitting === action.status}
                disabled={submitting !== null}
                onClick={(e) => {
                  e.stopPropagation();
                  void handleReview(action.status);
                }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 11,
                  color: action.tone,
                  borderColor: action.tone,
                }}
              >
                <action.icon style={{ width: 12, height: 12 }} />
                {t(`evidence.review.action.${action.status}`)}
              </Button>
            ))}
          </div>
        </div>
      }
    >
      {children}
    </Popover>
  );
}
