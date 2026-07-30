import { useCallback, useRef, useState } from "react";
import { Card, Tag, Typography } from "antd";
import { Loader2 } from "lucide-react";
import { useI18n } from "@/lib/i18n";

import type { ChatAction, ChatActionIntent } from "../types/actions";

const { Text } = Typography;


export interface ChatActionBubbleProps {
  action: ChatAction;
  onDispatch: (action: ChatAction) => void;
  /** If true, the action has already been dispatched — show disabled state. */
  dispatched?: boolean;
  /**
   * If true, show loading spinner and prevent re-dispatch.
   * The component also sets an internal loading flag on first click so that
   * the UI responds instantly, before the parent prop propagates.
   */
  loading?: boolean;
  /** Additional disable flag (e.g. parent component not mounted/ready). */
  disabled?: boolean;
}

export function ChatActionBubble({
  action,
  onDispatch,
  dispatched,
  loading = false,
  disabled = false,
}: ChatActionBubbleProps) {
  const { t } = useI18n();
  const INTENT_LABELS: Record<ChatActionIntent, string> = {
    "confirm-pipeline": t("chat.action.startPipeline"),
    "start-pipeline": t("chat.action.startPipeline"),
    "upload-pdf": t("chat.action.uploadPdf"),
    "search-evidence": t("chat.action.searchEvidence"),
    "classify-variant": t("chat.action.classifyVariant"),
    "interpret-evidence": t("chat.action.interpretEvidence"),
    "review-changes": t("chat.action.reviewQueue"),
    "check-pipeline-status": t("chat.action.taskManager"),
    "graph-qa": t("chat.action.graphQa"),
  };
  // Internal loading state flips on the first click so the UI immediately
  // shows a spinner and blocks further clicks, even before the parent's
  // `loading` / `dispatched` prop propagates.  Actions are one-way — once
  // dispatched or loading, they never revert, so no reset effect is needed.
  const [localLoading, setLocalLoading] = useState(false);
  // Ref-level guard catches synchronous double-clicks in the same event tick
  // before React batches the state update from setLocalLoading.
  const clickedRef = useRef(false);

  const isLoading = loading || localLoading;
  const isDisabled = dispatched || isLoading || disabled;

  const slotEntries = Object.entries(action.slots ?? {}).filter(
    ([, value]) => value !== undefined && value !== null && value !== "",
  );

  const handleDispatch = useCallback(() => {
    if (isDisabled) return;
    if (clickedRef.current) return;
    clickedRef.current = true;
    setLocalLoading(true);
    onDispatch(action);
  }, [action, isDisabled, onDispatch]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (isDisabled) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleDispatch();
      }
    },
    [handleDispatch, isDisabled],
  );

  const statusLabel = dispatched
    ? t("chat.action.dispatched")
    : isLoading
      ? t("chat.action.processing")
      : t("chat.action.clickToOpen");

  return (
    <Card
      size="small"
      style={{
        marginTop: 8,
        maxWidth: 480,
        cursor: isDisabled ? "not-allowed" : "pointer",
        opacity: isDisabled ? 0.6 : 1,
      }}
      styles={{ body: { padding: 12 } }}
      hoverable={!isDisabled}
      role="button"
      tabIndex={isDisabled ? -1 : 0}
      aria-disabled={isDisabled}
      aria-busy={isLoading}
      onClick={handleDispatch}
      onKeyDown={handleKeyDown}
      data-testid="chat-action-bubble"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Tag color="cyan">{INTENT_LABELS[action.intent]}</Tag>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {statusLabel}
        </Text>
        {isLoading && !dispatched && (
          <Loader2
            className="spin"
            style={{ marginLeft: "auto", width: 12, height: 12, color: "var(--color-primary-600, var(--color-primary-600))" }}
            aria-hidden="true"
          />
        )}
      </div>

      {slotEntries.length > 0 ? (
        <div style={{ marginTop: 8, display: "grid", gap: 4 }}>
          {slotEntries.map(([key, value]) => (
            <div key={key} style={{ fontSize: 12 }}>
              <Text strong>{key}</Text>
              <Text> · </Text>
              <Text code>{String(value)}</Text>
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
