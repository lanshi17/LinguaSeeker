import { Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import { formatRelative, formatTimestamp } from "@/lib/utils/format";
import type { ReviewAuditEventResponse, ReviewStatusValue } from "../types/audit";

interface AuditEventTableProps {
  events: ReviewAuditEventResponse[];
  loading?: boolean;
  onRowClick?: (event: ReviewAuditEventResponse) => void;
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

function getColumns(t: (key: string, params?: Record<string, unknown>) => string): ColumnsType<ReviewAuditEventResponse> {
  return [
    {
      title: t("audit.col.time"),
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      render: (iso: string) => (
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            fontVariantNumeric: "tabular-nums",
            color: "var(--color-text-secondary)",
          }}
          title={formatTimestamp(iso)}
        >
          {formatRelative(iso)}
        </span>
      ),
      sorter: (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      defaultSortOrder: "descend",
    },
    {
      title: t("audit.col.target"),
      dataIndex: "target_type",
      key: "target_type",
      width: 120,
      render: (type: string) => (
        <Typography.Text
          style={{
            fontSize: 12,
            fontFamily: "var(--font-mono)",
            color: "var(--color-text-strong)",
            backgroundColor: "var(--color-bg-muted)",
            padding: "2px 8px",
            borderRadius: 4,
          }}
        >
          {type}
        </Typography.Text>
      ),
    },
    {
      title: t("audit.col.transition"),
      key: "status",
      width: 220,
      render: (_, record) => {
        if (!record.old_status && !record.new_status) {
          return (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              —
            </Typography.Text>
          );
        }
        return (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            {record.old_status && (
              <Badge variant={STATUS_VARIANT[record.old_status] ?? "default"}>
                {record.old_status}
              </Badge>
            )}
            <ArrowRight style={{ width: 12, height: 12, color: "var(--color-text-muted)", flexShrink: 0 }} />
            {record.new_status && (
              <Badge variant={STATUS_VARIANT[record.new_status] ?? "default"}>
                {record.new_status}
              </Badge>
            )}
          </span>
        );
      },
      filters: [
        { text: "provisional → approved", value: "approved" },
        { text: "provisional → corrected", value: "corrected" },
        { text: "corrected → approved", value: "corrected-approved" },
        { text: "→ rejected", value: "rejected" },
      ],
      onFilter: (value, record) => {
        if (value === "corrected-approved") {
          return record.old_status === "corrected" && record.new_status === "approved";
        }
        return record.new_status === value;
      },
    },
    {
      title: t("audit.col.changes"),
      key: "changes",
      width: 100,
      render: (_, record) => {
        const count = record.field_deltas.length;
        return (
          <Typography.Text style={{ fontSize: 12, color: count > 0 ? "var(--color-text-strong)" : "var(--color-text-muted)" }}>
            {count > 0 ? `${count} field${count > 1 ? "s" : ""}` : t("audit.statusOnly")}
          </Typography.Text>
        );
      },
    },
    {
      title: t("audit.col.reason"),
      dataIndex: "change_reason",
      key: "change_reason",
      ellipsis: true,
      render: (reason: string | null) =>
        reason ? (
          <Typography.Text
            style={{ fontSize: 12, fontStyle: "italic", color: "var(--color-text-secondary)" }}
            ellipsis={{ tooltip: reason }}
          >
            {reason}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            —
          </Typography.Text>
        ),
    },
    {
      title: t("audit.col.eventId"),
      dataIndex: "review_event_id",
      key: "review_event_id",
      width: 120,
      render: (id: string) => (
        <Typography.Text
          style={{
            fontSize: 11,
            fontFamily: "var(--font-mono)",
            color: "var(--color-text-muted)",
          }}
          copyable={{ text: id }}
        >
          {id.slice(0, 8)}…
        </Typography.Text>
      ),
    },
  ];
}

export function AuditEventTable({ events, loading, onRowClick }: AuditEventTableProps) {
  const { t } = useI18n();
  const columns = getColumns(t);

  return (
    <Table<ReviewAuditEventResponse>
      columns={columns}
      dataSource={events}
      loading={loading}
      rowKey="review_event_id"
      size="small"
      pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => t("audit.events", { count: total }) }}
      onRow={(record) => ({
        onClick: () => onRowClick?.(record),
        style: { cursor: onRowClick ? "pointer" : undefined },
      })}
      scroll={{ x: 880 }}
      locale={{ emptyText: t("audit.noEvents") }}
    />
  );
}
