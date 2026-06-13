"use client";

import { Card, Tag, Typography } from "antd";

import type { ChatAction, ChatActionIntent } from "../types/actions";

const { Text } = Typography;

const INTENT_LABELS: Record<ChatActionIntent, string> = {
  "start-pipeline": "Start pipeline",
  "upload-pdf": "Upload PDF",
  "search-evidence": "Search evidence",
  "classify-variant": "Classify variant",
  "interpret-evidence": "Interpret evidence",
  "review-changes": "Review queue",
};

export interface ChatActionBubbleProps {
  action: ChatAction;
  onDispatch: (action: ChatAction) => void;
  dispatched?: boolean;
}

export function ChatActionBubble({
  action,
  onDispatch,
  dispatched,
}: ChatActionBubbleProps) {
  const slotEntries = Object.entries(action.slots ?? {}).filter(
    ([, value]) => value !== undefined && value !== null && value !== "",
  );

  return (
    <Card
      size="small"
      style={{ marginTop: 8, maxWidth: 480 }}
      styles={{ body: { padding: 12 } }}
      hoverable={!dispatched}
      onClick={() => {
        if (!dispatched) onDispatch(action);
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Tag color="cyan">{INTENT_LABELS[action.intent]}</Tag>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {dispatched ? "Dispatched" : "Click to open"}
        </Text>
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
