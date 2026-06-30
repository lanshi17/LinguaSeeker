import { Drawer, Typography, Descriptions, Tag } from "antd";
import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import { formatTimestamp } from "@/lib/utils/format";
import type { ReviewAuditEventResponse } from "@/lib/types/evidence";
import { STATUS_VARIANT } from "@/lib/constants/statusVariant";

interface AuditEventDetailDrawerProps {
  event: ReviewAuditEventResponse | null;
  open: boolean;
  onClose: () => void;
}


export function AuditEventDetailDrawer({
  event,
  open,
  onClose,
}: AuditEventDetailDrawerProps) {
  const { t } = useI18n();
  if (!event) return null;

  return (
    <Drawer
      title={t("audit.detail.title")}
      open={open}
      onClose={onClose}
      styles={{ body: { padding: "16px 24px" }, wrapper: { width: 480 } }}
    >
      <Descriptions column={1} size="small" labelStyle={{ fontWeight: 500, color: "var(--color-text-secondary)", fontSize: 12 }}>
        <Descriptions.Item label={t("audit.detail.eventId")}>
          <Typography.Text copyable style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
            {event.review_event_id}
          </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("audit.detail.evidenceId")}>
          <Typography.Text copyable style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
            {event.canonical_evidence_id}
          </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("audit.detail.reviewer")}>
          {event.reviewer_id ? (
            <Typography.Text copyable style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
              {event.reviewer_id}
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>{t("audit.detail.system")}</Typography.Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label={t("audit.detail.targetType")}>
          <Tag style={{ fontFamily: "var(--font-mono)", fontSize: 12, margin: 0 }}>
            {event.target_type}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label={t("audit.detail.time")}>
          <Typography.Text style={{ fontSize: 13 }}>
            {formatTimestamp(event.created_at)}
          </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label={t("audit.detail.transition")}>
          {event.old_status || event.new_status ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              {event.old_status && (
                <Badge variant={STATUS_VARIANT[event.old_status as keyof typeof STATUS_VARIANT] ?? "default"}>
                  {event.old_status}
                </Badge>
              )}
              <ArrowRight style={{ width: 14, height: 14, color: "var(--color-text-muted)" }} />
              {event.new_status && (
                <Badge variant={STATUS_VARIANT[event.new_status as keyof typeof STATUS_VARIANT] ?? "default"}>
                  {event.new_status}
                </Badge>
              )}
            </span>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>—</Typography.Text>
          )}
        </Descriptions.Item>
        {event.change_reason && (
          <Descriptions.Item label={t("audit.detail.reason")}>
            <Typography.Text style={{ fontSize: 13, fontStyle: "italic" }}>
              {event.change_reason}
            </Typography.Text>
          </Descriptions.Item>
        )}
      </Descriptions>

      {event.field_deltas.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 12 }}>
            {t("audit.detail.fieldChanges", { count: event.field_deltas.length })}
          </Typography.Text>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {event.field_deltas.map((delta) => (
              <div
                key={delta.field}
                style={{
                  borderRadius: 8,
                  border: "1px solid var(--color-border)",
                  padding: "10px 14px",
                  backgroundColor: "var(--color-bg-muted)",
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
                          color: "var(--color-error-text)",
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
