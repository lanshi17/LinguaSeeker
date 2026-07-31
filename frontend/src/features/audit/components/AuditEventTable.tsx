import { useState } from "react";
import { Table, Typography, Button } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ArrowRight, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import { formatRelative, formatTimestamp } from "@/lib/utils/format";
import type { ReviewAuditEventResponse, ReviewStatusValue } from "@/lib/types/evidence";
import { STATUS_VARIANT } from "@/lib/constants/statusVariant";

interface AuditEventTableProps {
  events: ReviewAuditEventResponse[];
  loading?: boolean;
  onRowClick?: (event: ReviewAuditEventResponse) => void;
  onQuickReview?: (evidenceId: string, status: ReviewStatusValue) => Promise<void>;
}

function getColumns(
  t: (key: string, params?: Record<string, unknown>) => string,
  onQuickReview?: (evidenceId: string, status: ReviewStatusValue) => Promise<void>,
): ColumnsType<ReviewAuditEventResponse> {
  const cols: ColumnsType<ReviewAuditEventResponse> = [
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
      title: t("audit.col.reviewer"),
      key: "reviewer",
      width: 130,
      render: (_, record) =>
        record.reviewer_id ? (
          <Typography.Text style={{ fontSize: 12 }}>{record.reviewer_id}</Typography.Text>
        ) : (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {t("audit.detail.system")}
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
              <Badge variant={STATUS_VARIANT[record.old_status as keyof typeof STATUS_VARIANT] ?? "default"}>
                {record.old_status}
              </Badge>
            )}
            <ArrowRight style={{ width: 12, height: 12, color: "var(--color-text-muted)", flexShrink: 0 }} />
            {record.new_status && (
              <Badge variant={STATUS_VARIANT[record.new_status as keyof typeof STATUS_VARIANT] ?? "default"}>
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

  if (onQuickReview) {
    cols.push({
      title: t("audit.col.actions"),
      key: "actions",
      width: 160,
      render: (_, record) => {
        if (record.new_status !== "provisional") return null;
        return <QuickReviewButtons evidenceId={record.canonical_evidence_id} onQuickReview={onQuickReview} />;
      },
    });
  }

  return cols;
}

function QuickReviewButtons({
  evidenceId,
  onQuickReview,
}: {
  evidenceId: string;
  onQuickReview: (evidenceId: string, status: ReviewStatusValue) => Promise<void>;
}) {
  const { t } = useI18n();
  const [loading, setLoading] = useState<ReviewStatusValue | null>(null);

  const handleClick = async (status: ReviewStatusValue) => {
    setLoading(status);
    try {
      await onQuickReview(evidenceId, status);
    } finally {
      setLoading(null);
    }
  };

  return (
    <span style={{ display: "inline-flex", gap: 4 }}>
      <Button
        type="link"
        size="small"
        loading={loading === "approved"}
        disabled={loading !== null}
        icon={<CheckCircle2 style={{ width: 12, height: 12 }} />}
        onClick={(e) => {
          e.stopPropagation();
          void handleClick("approved");
        }}
        style={{ fontSize: 11, color: "var(--color-success-text, var(--color-success-600))", padding: "0 4px" }}
      >
        {t("audit.action.approve")}
      </Button>
      <Button
        type="link"
        size="small"
        loading={loading === "rejected"}
        disabled={loading !== null}
        icon={<XCircle style={{ width: 12, height: 12 }} />}
        onClick={(e) => {
          e.stopPropagation();
          void handleClick("rejected");
        }}
        style={{ fontSize: 11, color: "var(--color-error-text, var(--color-error-500))", padding: "0 4px" }}
      >
        {t("audit.action.reject")}
      </Button>
    </span>
  );
}

export function AuditEventTable({ events, loading, onRowClick, onQuickReview }: AuditEventTableProps) {
  const { t } = useI18n();
  const columns = getColumns(t, onQuickReview);

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
      scroll={{ x: 1040 }}
      locale={{ emptyText: t("audit.noEvents") }}
    />
  );
}
