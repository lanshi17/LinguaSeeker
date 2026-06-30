import { useMemo, useState, useCallback } from "react";
import { Button, Input, Segmented, Flex, Typography, App } from "antd";
import { Search, ClipboardCheck } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { MetricTile } from "@/components/ui/MetricTile";
import { useI18n } from "@/lib/i18n";
import { useAuditEvents } from "../hooks/useAuditEvents";
import { AuditEventTable } from "./AuditEventTable";
import { AuditEventDetailDrawer } from "./AuditEventDetailDrawer";
import { EvidenceReviewDrawer } from "./EvidenceReviewDrawer";
import { patchEvidence } from "@/features/evidence-search/services/evidenceCorrection";
import type { ReviewAuditEventResponse, ReviewStatusValue } from "@/lib/types/evidence";

type StatusFilter = "all" | "provisional" | "approved" | "corrected" | "rejected";

export function AuditView() {
  const { t } = useI18n();
  const { data: events, isLoading } = useAuditEvents({ limit: 500 });
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<ReviewAuditEventResponse | null>(null);
  const [reviewDrawerOpen, setReviewDrawerOpen] = useState(false);
  const { message } = App.useApp();
  const queryClient = useQueryClient();

  const handleQuickReview = useCallback(async (evidenceId: string, status: ReviewStatusValue) => {
    try {
      await patchEvidence(evidenceId, { fields: {}, new_status: status });
      message.success(t("audit.quickReview.success", { status }));
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    } catch {
      message.error(t("audit.quickReview.error"));
    }
  }, [message, queryClient, t]);

  const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
    { value: "all", label: t("audit.filter.all") },
    { value: "provisional", label: t("audit.filter.provisional") },
    { value: "approved", label: t("audit.filter.approved") },
    { value: "corrected", label: t("audit.filter.corrected") },
    { value: "rejected", label: t("audit.filter.rejected") },
  ];

  const filtered = useMemo(() => {
    if (!events) return [];
    let result = events;

    if (statusFilter !== "all") {
      result = result.filter((e) => e.new_status === statusFilter);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.canonical_evidence_id.toLowerCase().includes(q) ||
          e.target_type.toLowerCase().includes(q) ||
          (e.change_reason?.toLowerCase().includes(q) ?? false) ||
          e.field_deltas.some((d) => d.field.toLowerCase().includes(q)),
      );
    }

    return result;
  }, [events, statusFilter, search]);

  const stats = useMemo(() => {
    if (!events) return { total: 0, approved: 0, corrected: 0, rejected: 0 };
    return {
      total: events.length,
      approved: events.filter((e) => e.new_status === "approved").length,
      corrected: events.filter((e) => e.new_status === "corrected").length,
      rejected: events.filter((e) => e.new_status === "rejected").length,
    };
  }, [events]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Summary stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
        }}
      >
        <MetricTile label={t("audit.metric.total")} value={stats.total} tone="primary" />
        <MetricTile label={t("audit.metric.approved")} value={stats.approved} tone="success" />
        <MetricTile label={t("audit.metric.corrected")} value={stats.corrected} tone="warning" />
        <MetricTile label={t("audit.metric.rejected")} value={stats.rejected} tone="error" />
      </div>

      {/* Filters */}
      <Flex gap={12} align="center" wrap="wrap" justify="space-between">
        <Flex gap={12} align="center" wrap="wrap">
          <Segmented
            value={statusFilter}
            onChange={(val) => setStatusFilter(val as StatusFilter)}
            options={STATUS_FILTERS}
          />
          <Input
            placeholder={t("audit.searchPh")}
            prefix={<Search style={{ width: 14, height: 14, color: "var(--color-text-muted)" }} />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ maxWidth: 320 }}
            allowClear
          />
          {filtered.length < (events?.length ?? 0) && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("audit.showing", { count: filtered.length, total: events?.length ?? 0 })}
            </Typography.Text>
          )}
        </Flex>
        <Button
          type="primary"
          icon={<ClipboardCheck style={{ width: 14, height: 14 }} />}
          onClick={() => setReviewDrawerOpen(true)}
        >
          {t("audit.reviewEvidence")}
        </Button>
      </Flex>

      {/* Table */}
      <AuditEventTable
        events={filtered}
        loading={isLoading}
        onRowClick={setSelectedEvent}
        onQuickReview={handleQuickReview}
      />

      {/* Detail drawer */}
      <AuditEventDetailDrawer
        event={selectedEvent}
        open={selectedEvent !== null}
        onClose={() => setSelectedEvent(null)}
      />

      {/* Evidence review drawer */}
      <EvidenceReviewDrawer
        open={reviewDrawerOpen}
        onClose={() => setReviewDrawerOpen(false)}
      />
    </div>
  );
}
