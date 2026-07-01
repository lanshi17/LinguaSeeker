/**
 * Right-click / left-click context menu for evidence highlight marks.
 *
 * Architecture:
 *  - <FieldReviewMenu /> renders once per page (portal to body).
 *  - Each <mark> gets onClick/onContextMenu that calls openFieldReviewMenu(e, info).
 *  - The menu uses simple React state — no module-level globals.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { App, Button } from "antd";
import { Badge } from "@/components/ui/Badge";
import { CheckCircle2, XCircle, Pencil } from "lucide-react";
import { patchEvidence } from "../services/evidenceCorrection";
import type { ReviewStatusValue } from "@/lib/types/evidence";
import { useI18n } from "@/lib/i18n";

export interface FieldReviewInfo {
  evidenceId: string;
  fieldId: string;
  label: string;
  category?: string | null;
  currentStatus: string;
  value?: string | null;
  groupId: string;
}

const QUICK_ACTIONS: { status: ReviewStatusValue; icon: typeof CheckCircle2; tone: string }[] = [
  { status: "approved", icon: CheckCircle2, tone: "var(--color-success-text, #16a34a)" },
  { status: "corrected", icon: Pencil, tone: "var(--color-warning-text, #d97706)" },
  { status: "rejected", icon: XCircle, tone: "var(--color-error-text, #dc2626)" },
];

// ── Shared ref — allows openFieldReviewMenu to reach the menu's setState ──
type PosState = { x: number; y: number; info: FieldReviewInfo } | null;
const _menuRef: { current: ((s: PosState) => void) | null } = { current: null };

/** Call from any <mark>'s onClick to open the review menu. */
export function openFieldReviewMenu(e: React.MouseEvent, info: FieldReviewInfo) {
  e.preventDefault();
  e.stopPropagation();
  _menuRef.current?.({ x: e.clientX, y: e.clientY, info });
}

/** Standalone menu component — render once per page. */
export function FieldReviewMenu() {
  const { t } = useI18n();
  const { message } = App.useApp();
  const [pos, setPos] = useState<PosState>(null);
  const [submitting, setSubmitting] = useState<ReviewStatusValue | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Register this instance's setState so openFieldReviewMenu can call it
  useEffect(() => {
    _menuRef.current = setPos;
    return () => { _menuRef.current = null; };
  }, []);

  const handleReview = useCallback(
    async (status: ReviewStatusValue) => {
      if (!pos) return;
      setSubmitting(status);
      try {
        await patchEvidence(pos.info.evidenceId, { fields: {}, new_status: status });
        message.success(t("evidence.review.success", { status }));
        setPos(null);
      } catch {
        message.error(t("evidence.review.error"));
      } finally {
        setSubmitting(null);
      }
    },
    [pos, message, t],
  );

  // Close on click outside (delayed to avoid closing on the same click that opened)
  useEffect(() => {
    if (!pos) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setPos(null);
      }
    };
    const id = setTimeout(() => document.addEventListener("mousedown", handler), 10);
    return () => { clearTimeout(id); document.removeEventListener("mousedown", handler); };
  }, [pos]);

  // Close on Escape
  useEffect(() => {
    if (!pos) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setPos(null); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [pos]);

  if (!pos) return null;

  const statusBadge: Record<string, "default" | "success" | "warning" | "error"> = {
    provisional: "default",
    approved: "success",
    corrected: "warning",
    rejected: "error",
  };

  return createPortal(
    <div
      ref={menuRef}
      onMouseDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      style={{
        position: "fixed",
        left: pos.x,
        top: pos.y,
        zIndex: 1100,
        minWidth: 220,
        background: "var(--color-surface)",
        borderRadius: 8,
        boxShadow: "0 8px 24px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.08)",
        border: "1px solid var(--color-border)",
        padding: 0,
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "10px 14px 8px", borderBottom: "1px solid var(--color-bg-muted)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-strong)" }}>
            {pos.info.label}
          </span>
          <Badge variant={statusBadge[pos.info.currentStatus] ?? "default"} style={{ fontSize: 10 }}>
            {pos.info.currentStatus}
          </Badge>
        </div>
        <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
          {pos.info.fieldId}
        </span>
        {pos.info.value && (
          <p style={{
            fontSize: 12, lineHeight: "18px", color: "var(--color-text-secondary)",
            margin: "4px 0 0", maxHeight: 54, overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {pos.info.value}
          </p>
        )}
      </div>

      <div style={{ padding: "6px 4px" }}>
        {QUICK_ACTIONS.filter((a) => a.status !== pos.info.currentStatus).map((action) => (
          <Button
            key={action.status}
            type="text"
            block
            loading={submitting === action.status}
            disabled={submitting !== null}
            onClick={(e) => { e.stopPropagation(); void handleReview(action.status); }}
            style={{
              display: "flex", alignItems: "center", gap: 8,
              fontSize: 12, height: 32, color: action.tone,
              justifyContent: "flex-start", padding: "0 10px",
            }}
          >
            <action.icon style={{ width: 14, height: 14 }} />
            {t(`evidence.review.action.${action.status}`)}
          </Button>
        ))}
      </div>
    </div>,
    document.body,
  );
}
