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

const SAMPLE_EVENTS: ReviewAuditEventResponse[] = [
  {
    review_event_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    canonical_evidence_id: "ce-0001-ABCA4-pathogenic",
    reviewer_id: null,
    target_type: "evidence_extraction",
    old_status: null,
    new_status: "provisional",
    field_deltas: [],
    change_reason: "Auto-extracted from PMID:31234567",
    created_at: "2026-07-01T09:12:00Z",
  },
  {
    review_event_id: "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    canonical_evidence_id: "ce-0002-MECP2-likely-pathogenic",
    reviewer_id: null,
    target_type: "evidence_extraction",
    old_status: null,
    new_status: "provisional",
    field_deltas: [],
    change_reason: "Auto-extracted from PMID:28765432",
    created_at: "2026-07-01T09:15:00Z",
  },
  {
    review_event_id: "c3d4e5f6-a7b8-9012-cdef-123456789012",
    canonical_evidence_id: "ce-0001-ABCA4-pathogenic",
    reviewer_id: "user-reviewer-01",
    target_type: "evidence_review",
    old_status: "provisional",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Extraction verified against source document",
    created_at: "2026-07-01T10:30:00Z",
  },
  {
    review_event_id: "d4e5f6a7-b8c9-0123-defa-234567890123",
    canonical_evidence_id: "ce-0003-FOXP2-vus",
    reviewer_id: null,
    target_type: "evidence_extraction",
    old_status: null,
    new_status: "provisional",
    field_deltas: [],
    change_reason: "Auto-extracted from PMID:33456789",
    created_at: "2026-07-01T11:00:00Z",
  },
  {
    review_event_id: "e5f6a7b8-c9d0-1234-efab-345678901234",
    canonical_evidence_id: "ce-0002-MECP2-likely-pathogenic",
    reviewer_id: "user-reviewer-01",
    target_type: "evidence_correction",
    old_status: "provisional",
    new_status: "corrected",
    field_deltas: [
      { field: "gene", old_value: "MECP", new_value: "MECP2" },
      { field: "disease", old_value: "Rett syndrome", new_value: "Rett syndrome (OMIM:312750)" },
    ],
    change_reason: "Corrected gene symbol and added OMIM ID",
    created_at: "2026-07-01T14:20:00Z",
  },
  {
    review_event_id: "f6a7b8c9-d0e1-2345-fabc-456789012345",
    canonical_evidence_id: "ce-0003-FOXP2-vus",
    reviewer_id: "user-reviewer-02",
    target_type: "evidence_review",
    old_status: "provisional",
    new_status: "rejected",
    field_deltas: [],
    change_reason: "Duplicate of evidence item ce-0014; source misattributed",
    created_at: "2026-07-01T15:45:00Z",
  },
  {
    review_event_id: "a7b8c9d0-e1f2-3456-abcd-567890123456",
    canonical_evidence_id: "ce-0002-MECP2-likely-pathogenic",
    reviewer_id: "user-reviewer-01",
    target_type: "evidence_review",
    old_status: "corrected",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Correction verified — gene symbol and OMIM ID confirmed",
    created_at: "2026-07-02T08:10:00Z",
  },
  {
    review_event_id: "b8c9d0e1-f2a3-4567-bcde-678901234567",
    canonical_evidence_id: "ce-0004-SCN1A-pathogenic",
    reviewer_id: null,
    target_type: "evidence_extraction",
    old_status: null,
    new_status: "provisional",
    field_deltas: [],
    change_reason: "Auto-extracted from PMID:34567890",
    created_at: "2026-07-02T08:30:00Z",
  },
  {
    review_event_id: "c9d0e1f2-a3b4-5678-cdef-789012345678",
    canonical_evidence_id: "ce-0004-SCN1A-pathogenic",
    reviewer_id: "user-reviewer-02",
    target_type: "evidence_correction",
    old_status: "provisional",
    new_status: "corrected",
    field_deltas: [
      { field: "variant", old_value: "p.Arg1648His", new_value: "p.Arg1648His (c.4943G>A)" },
      { field: "evidence_strength", old_value: "Moderate", new_value: "Strong" },
    ],
    change_reason: "Added cDNA notation; upgraded strength per ClinGen SVI guidance",
    created_at: "2026-07-02T09:15:00Z",
  },
  {
    review_event_id: "d0e1f2a3-b4c5-6789-defa-890123456789",
    canonical_evidence_id: "ce-0005-KCNQ2-likely-benign",
    reviewer_id: null,
    target_type: "evidence_extraction",
    old_status: null,
    new_status: "provisional",
    field_deltas: [],
    change_reason: "Auto-extracted from PMID:35678901",
    created_at: "2026-07-02T10:00:00Z",
  },
];

export function AuditView() {
  const { t } = useI18n();
  const { data: events, isLoading } = useAuditEvents({ limit: 500 });
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<ReviewAuditEventResponse | null>(null);
  const [reviewDrawerOpen, setReviewDrawerOpen] = useState(false);
  const { message } = App.useApp();
  const queryClient = useQueryClient();

  const effectiveEvents = useMemo(
    () => (!events || events.length === 0 ? SAMPLE_EVENTS : events),
    [events],
  );

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
    let result = effectiveEvents;

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
  }, [effectiveEvents, statusFilter, search]);

  const stats = useMemo(() => {
    return {
      total: effectiveEvents.length,
      approved: effectiveEvents.filter((e) => e.new_status === "approved").length,
      corrected: effectiveEvents.filter((e) => e.new_status === "corrected").length,
      rejected: effectiveEvents.filter((e) => e.new_status === "rejected").length,
    };
  }, [effectiveEvents]);

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
          {filtered.length < effectiveEvents.length && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("audit.showing", { count: filtered.length, total: effectiveEvents.length })}
            </Typography.Text>
          )}
        </Flex>
        <Button
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
