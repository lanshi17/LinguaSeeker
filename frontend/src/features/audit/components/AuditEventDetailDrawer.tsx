import { Drawer, Typography, Descriptions, Tag } from "antd";
import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { formatTimestamp } from "@/lib/utils/format";
import type { ReviewAuditEventResponse, ReviewStatusValue } from "../types/audit";

interface AuditEventDetailDrawerProps {
  event: ReviewAuditEventResponse | null;
  open: boolean;
  onClose: () => void;
}

const STATUS_VARIANT: Record<
  ReviewStatusValue,
  "default" | "success" | "warning" | "error"
> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

export function AuditEventDetailDrawer({
  event,
  open,
  onClose,
}: AuditEventDetailDrawerProps) {
  if (!event) return null;

  return (
    <Drawer
      title="Audit Event Detail"
      open={open}
      onClose={onClose}
      styles={{ body: { padding: "16px 24px" }, wrapper: { width: 480 } }}
    >
      <Descriptions column={1} size="small" labelStyle={{ fontWeight: 500, color: "#6b7280", fontSize: 12 }}>
        <Descriptions.Item label="Event ID">
          <Typography.Text copyable style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
            {event.review_event_id}
          </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="Evidence ID">
          <Typography.Text copyable style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
            {event.canonical_evidence_id}
          </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="Reviewer">
          {event.reviewer_id ? (
            <Typography.Text copyable style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
              {event.reviewer_id}
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>System</Typography.Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Target type">
          <Tag style={{ fontFamily: "var(--font-mono)", fontSize: 12, margin: 0 }}>
            {event.target_type}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Time">
          <Typography.Text style={{ fontSize: 13 }}>
            {formatTimestamp(event.created_at)}
          </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="Status transition">
          {event.old_status || event.new_status ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              {event.old_status && (
                <Badge variant={STATUS_VARIANT[event.old_status] ?? "default"}>
                  {event.old_status}
                </Badge>
              )}
              <ArrowRight style={{ width: 14, height: 14, color: "#9ca3af" }} />
              {event.new_status && (
                <Badge variant={STATUS_VARIANT[event.new_status] ?? "default"}>
                  {event.new_status}
                </Badge>
              )}
            </span>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>—</Typography.Text>
          )}
        </Descriptions.Item>
        {event.change_reason && (
          <Descriptions.Item label="Reason">
            <Typography.Text style={{ fontSize: 13, fontStyle: "italic" }}>
              {event.change_reason}
            </Typography.Text>
          </Descriptions.Item>
        )}
      </Descriptions>

      {event.field_deltas.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 12 }}>
            Field changes ({event.field_deltas.length})
          </Typography.Text>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {event.field_deltas.map((delta) => (
              <div
                key={delta.field}
                style={{
                  borderRadius: 8,
                  border: "1px solid #e5e7eb",
                  padding: "10px 14px",
                  backgroundColor: "#fafafa",
                }}
              >
                <Typography.Text
                  strong
                  style={{
                    fontSize: 12,
                    fontFamily: "var(--font-mono)",
                    color: "var(--color-primary-700)",
                    display: "block",
                    marginBottom: 6,
                  }}
                >
                  {delta.field}
                </Typography.Text>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {delta.old_value && (
                    <div style={{ fontSize: 12 }}>
                      <Typography.Text type="secondary" style={{ fontSize: 11, marginRight: 6 }}>
                        −
                      </Typography.Text>
                      <Typography.Text
                        style={{
                          fontSize: 12,
                          color: "#dc2626",
                          textDecoration: "line-through",
                        }}
                      >
                        {delta.old_value}
                      </Typography.Text>
                    </div>
                  )}
                  {delta.new_value && (
                    <div style={{ fontSize: 12 }}>
                      <Typography.Text type="secondary" style={{ fontSize: 11, marginRight: 6 }}>
                        +
                      </Typography.Text>
                      <Typography.Text
                        style={{
                          fontSize: 12,
                          color: "var(--color-success-700)",
                        }}
                      >
                        {delta.new_value}
                      </Typography.Text>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Drawer>
  );
}
