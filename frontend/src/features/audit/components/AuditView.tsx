import { useMemo, useState, useCallback } from "react";
import { Button, Input, Segmented, Flex, Typography, App } from "antd";
import { Search, ClipboardCheck } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useI18n } from "@/lib/i18n";
import { useAuditEvents } from "../hooks/useAuditEvents";
import { AuditEventTable } from "./AuditEventTable";
import { AuditEventDetailDrawer } from "./AuditEventDetailDrawer";
import { EvidenceReviewDrawer } from "./EvidenceReviewDrawer";
import { patchEvidence } from "@/features/evidence-search/services/evidenceCorrection";
import type { ReviewAuditEventResponse, ReviewStatusValue } from "@/lib/types/evidence";

type StatusFilter = "all" | "provisional" | "approved" | "corrected" | "rejected";

/**
 * Demo audit trail — shown when the backend has no curated review content
 * (empty result, or only bare auto-generated events). Mirrors the real
 * system: `evidence_item` target type, catalog field IDs (A.* / B.* / D.* /
 * F.* / J.* / K.*), and a coherent review workflow with human reviewers.
 */
const REVIEWERS = ["zhang.wei", "liu.yang", "wang.jing", "chen.hao", "zhao.min"];

function extractionEvent(
  eventId: string,
  evidenceId: string,
  pmid: string,
  createdAt: string,
): ReviewAuditEventResponse {
  return {
    review_event_id: eventId,
    canonical_evidence_id: evidenceId,
    reviewer_id: null,
    target_type: "evidence_item",
    old_status: null,
    new_status: "provisional",
    field_deltas: [],
    change_reason: `Auto-extracted from PMID:${pmid}`,
    created_at: createdAt,
  };
}

const SAMPLE_EVENTS: ReviewAuditEventResponse[] = [
  // ── Batch import 2026-07-08 ─────────────────────────────────────────
  extractionEvent("0a1f2b3c-4d5e-4f67-8a9b-c0d1e2f3a4b5", "ce-0001-ABCA4-pathogenic", "31234567", "2026-07-08T01:12:00Z"),
  extractionEvent("1b2c3d4e-5f60-4a71-9b8c-d1e2f3a4b5c6", "ce-0002-MECP2-likely-pathogenic", "28765432", "2026-07-08T01:12:30Z"),
  extractionEvent("2c3d4e5f-6071-4a82-9b9d-e2f3a4b5c6d7", "ce-0003-FOXP2-vus", "33456789", "2026-07-08T01:13:00Z"),
  extractionEvent("3d4e5f60-7182-4a93-9bae-f3a4b5c6d7e8", "ce-0004-SCN1A-pathogenic", "34567890", "2026-07-08T01:15:00Z"),
  extractionEvent("4e5f6071-8293-4aa4-9bbf-a4b5c6d7e8f9", "ce-0005-KCNQ2-likely-benign", "35678901", "2026-07-08T01:15:30Z"),

  // ── Day 1 curation ──────────────────────────────────────────────────
  {
    review_event_id: "5f607182-93a4-4bb5-9cc0-b5c6d7e8f90a",
    canonical_evidence_id: "ce-0001-ABCA4-pathogenic",
    reviewer_id: REVIEWERS[0],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Extraction verified against source PDF (pp. 3–5); ACMG criteria PS3 + PM2 + PP3 documented",
    created_at: "2026-07-08T02:30:00Z",
  },
  {
    review_event_id: "60718293-a4b5-4cc6-9dd1-c6d7e8f90a1b",
    canonical_evidence_id: "ce-0002-MECP2-likely-pathogenic",
    reviewer_id: REVIEWERS[1],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "corrected",
    field_deltas: [
      { field: "A.gene_symbol", old_value: "MECP", new_value: "MECP2" },
      { field: "B.disease_diagnosis", old_value: "Rett syndrome", new_value: "Rett syndrome (OMIM 312750)" },
    ],
    change_reason: "Gene symbol corrected per HGNC; OMIM identifier added from source",
    created_at: "2026-07-08T06:20:00Z",
  },
  {
    review_event_id: "718293a4-b5c6-4dd7-9ee2-d7e8f90a1b2c",
    canonical_evidence_id: "ce-0003-FOXP2-vus",
    reviewer_id: REVIEWERS[2],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "rejected",
    field_deltas: [],
    change_reason: "Duplicate of evidence extracted from the same cohort (PMID:36123456); source misattributed",
    created_at: "2026-07-08T07:45:00Z",
  },

  // ── Batch import 2026-07-09 ─────────────────────────────────────────
  extractionEvent("8293a4b5-c6d7-4ee8-9ff3-e8f90a1b2c3d", "ce-0006-MYO7A-pathogenic", "36789012", "2026-07-09T00:30:00Z"),
  extractionEvent("93a4b5c6-d7e8-4ff9-9004-f90a1b2c3d4e", "ce-0007-FBN1-pathogenic", "37890123", "2026-07-09T00:31:00Z"),
  extractionEvent("a4b5c6d7-e8f9-400a-8115-0a1b2c3d4e5f", "ce-0008-CFTR-pathogenic", "38901234", "2026-07-09T00:40:00Z"),
  extractionEvent("b5c6d7e8-f90a-411b-9226-1b2c3d4e5f60", "ce-0009-GJB2-pathogenic", "39012345", "2026-07-09T00:41:00Z"),
  extractionEvent("c6d7e8f9-0a1b-422c-a337-2c3d4e5f6071", "ce-0010-DMD-likely-pathogenic", "40123456", "2026-07-09T00:45:00Z"),

  // ── Day 2 curation ──────────────────────────────────────────────────
  {
    review_event_id: "d7e8f90a-1b2c-433d-b448-3d4e5f607182",
    canonical_evidence_id: "ce-0004-SCN1A-pathogenic",
    reviewer_id: REVIEWERS[3],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "corrected",
    field_deltas: [
      { field: "A.variant_hgvs_c", old_value: null, new_value: "c.4943G>A" },
      { field: "F.evidence_strength_tier", old_value: "Moderate", new_value: "Strong" },
    ],
    change_reason: "cDNA notation added per HGVS; strength upgraded per ClinGen SVI guidance",
    created_at: "2026-07-09T01:15:00Z",
  },
  {
    review_event_id: "e8f90a1b-2c3d-444e-c559-4e5f60718293",
    canonical_evidence_id: "ce-0005-KCNQ2-likely-benign",
    reviewer_id: REVIEWERS[0],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "approved",
    field_deltas: [],
    change_reason: "gnomAD v4.1 MAF 0.012 exceeds BS1 threshold — consistent with benign assertion",
    created_at: "2026-07-09T02:05:00Z",
  },
  {
    review_event_id: "f90a1b2c-3d4e-455f-d66a-5f60718293a4",
    canonical_evidence_id: "ce-0002-MECP2-likely-pathogenic",
    reviewer_id: REVIEWERS[1],
    target_type: "evidence_item",
    old_status: "corrected",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Correction verified against source PDF p. 7; HGNC symbol and OMIM ID confirmed",
    created_at: "2026-07-10T01:40:00Z",
  },
  {
    review_event_id: "0a1b2c3d-4e5f-4660-e77b-60718293a4b5",
    canonical_evidence_id: "ce-0006-MYO7A-pathogenic",
    reviewer_id: REVIEWERS[4],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "corrected",
    field_deltas: [
      { field: "B.ancestry_or_population", old_value: "Chinese Han", new_value: "Chinese Han (consanguineous)" },
      { field: "B.mode_of_inheritance_reported", old_value: "autosomal recessive", new_value: "autosomal recessive (consanguineous pedigree)" },
    ],
    change_reason: "Consanguinity flagged from pedigree (Fig. 2A); ancestry and inheritance fields updated",
    created_at: "2026-07-10T03:20:00Z",
  },
  {
    review_event_id: "1b2c3d4e-5f60-4771-f88c-718293a4b5c6",
    canonical_evidence_id: "ce-0007-FBN1-pathogenic",
    reviewer_id: REVIEWERS[2],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Segregation confirmed in 3 affected relatives (Table 2); PM2 + PP1 applied",
    created_at: "2026-07-10T05:50:00Z",
  },
  {
    review_event_id: "2c3d4e5f-6071-4882-009d-8293a4b5c6d7",
    canonical_evidence_id: "ce-0008-CFTR-pathogenic",
    reviewer_id: REVIEWERS[3],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "corrected",
    field_deltas: [
      { field: "A.variant_hgvs_c", old_value: "c.1521delCTT", new_value: "c.1521_1523delCTT" },
      { field: "A.variant_legacy_name", old_value: null, new_value: "ΔF508" },
    ],
    change_reason: "HGVS range notation corrected; legacy ΔF508 alias added",
    created_at: "2026-07-11T01:30:00Z",
  },
  {
    review_event_id: "3d4e5f60-7182-4993-11ae-93a4b5c6d7e8",
    canonical_evidence_id: "ce-0006-MYO7A-pathogenic",
    reviewer_id: REVIEWERS[0],
    target_type: "evidence_item",
    old_status: "corrected",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Correction verified — pedigree consistent with autosomal recessive inheritance",
    created_at: "2026-07-11T08:10:00Z",
  },

  // ── Batch import 2026-07-12 ─────────────────────────────────────────
  extractionEvent("4e5f6071-8293-4aa4-22bf-a4b5c6d7e8f9", "ce-0011-LMNA-vus", "41234567", "2026-07-12T02:00:00Z"),
  extractionEvent("5f607182-93a4-4bb5-33c0-b5c6d7e8f90a", "ce-0012-COL4A5-pathogenic", "42345678", "2026-07-12T02:01:00Z"),
  {
    review_event_id: "60718293-a4b5-4cc6-44d1-c6d7e8f90a1b",
    canonical_evidence_id: "ce-0009-GJB2-pathogenic",
    reviewer_id: REVIEWERS[1],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Founder allele — carrier frequency 2.8% in East Asian controls; PM3 + PVS1 applied",
    created_at: "2026-07-12T03:10:00Z",
  },
  {
    review_event_id: "718293a4-b5c6-4dd7-55e2-d7e8f90a1b2c",
    canonical_evidence_id: "ce-0010-DMD-likely-pathogenic",
    reviewer_id: REVIEWERS[4],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Nonsense variant in exon 62 — PVS1 + PM2_Supporting; consistent with Duchenne phenotype",
    created_at: "2026-07-12T06:30:00Z",
  },
  {
    review_event_id: "8293a4b5-c6d7-4ee8-66f3-e8f90a1b2c3d",
    canonical_evidence_id: "ce-0012-COL4A5-pathogenic",
    reviewer_id: REVIEWERS[2],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "rejected",
    field_deltas: [],
    change_reason: "Variant absent on BAM re-review — low-depth sequencing artifact; evidence group discarded",
    created_at: "2026-07-12T08:00:00Z",
  },

  // ── Batch import 2026-07-15 ─────────────────────────────────────────
  extractionEvent("93a4b5c6-d7e8-4ff9-7704-f90a1b2c3d4e", "ce-0013-MYH7-likely-pathogenic", "43456789", "2026-07-15T01:05:00Z"),
  extractionEvent("a4b5c6d7-e8f9-400a-8815-0a1b2c3d4e5f", "ce-0014-SCN5A-vus", "44567890", "2026-07-15T01:06:00Z"),
  {
    review_event_id: "b5c6d7e8-f90a-411b-9926-1b2c3d4e5f60",
    canonical_evidence_id: "ce-0004-SCN1A-pathogenic",
    reviewer_id: REVIEWERS[0],
    target_type: "evidence_item",
    old_status: "corrected",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Corrections verified against source PDF p. 5; Dravet phenotype consistent with SCN1A loss-of-function",
    created_at: "2026-07-15T02:20:00Z",
  },
  {
    review_event_id: "c6d7e8f9-0a1b-422c-aa37-2c3d4e5f6071",
    canonical_evidence_id: "ce-0008-CFTR-pathogenic",
    reviewer_id: REVIEWERS[2],
    target_type: "evidence_item",
    old_status: "corrected",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Confirmed against CFTR2 variant table; p.Phe508del is the most common CF-causing allele",
    created_at: "2026-07-20T03:30:00Z",
  },
  {
    review_event_id: "d7e8f90a-1b2c-433d-bb48-3d4e5f607182",
    canonical_evidence_id: "ce-0013-MYH7-likely-pathogenic",
    reviewer_id: REVIEWERS[4],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "corrected",
    field_deltas: [
      { field: "D.population_database_name", old_value: "gnomAD v2.1", new_value: "gnomAD v4.1" },
      { field: "D.allele_frequency", old_value: "Absent", new_value: "0.00008" },
    ],
    change_reason: "Allele frequency updated to gnomAD v4.1; PM2_Supporting retained per ClinGen recommendation",
    created_at: "2026-07-22T07:30:00Z",
  },
  {
    review_event_id: "e8f90a1b-2c3d-444e-cc59-4e5f60718293",
    canonical_evidence_id: "ce-0011-LMNA-vus",
    reviewer_id: REVIEWERS[3],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "corrected",
    field_deltas: [
      { field: "J.clinvar_assertion", old_value: "VUS (2 submissions)", new_value: "Pathogenic (3 submissions)" },
      { field: "K.gene_disease_validity_classification", old_value: "Definitive", new_value: "Definitive (ClinGen GCEP 2025-12)" },
    ],
    change_reason: "ClinVar assertion refreshed — recent submissions reclassify as pathogenic; awaiting final review",
    created_at: "2026-07-24T06:40:00Z",
  },
  {
    review_event_id: "f90a1b2c-3d4e-455f-dd6a-5f60718293a4",
    canonical_evidence_id: "ce-0014-SCN5A-vus",
    reviewer_id: REVIEWERS[1],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "rejected",
    field_deltas: [],
    change_reason: "Functional evidence contradicts pathogenicity — minigene assay shows no aberrant splicing (Fig. 3)",
    created_at: "2026-07-28T03:40:00Z",
  },
  {
    review_event_id: "0a1b2c3d-4e5f-4660-ee7b-60718293a4b5",
    canonical_evidence_id: "ce-0013-MYH7-likely-pathogenic",
    reviewer_id: REVIEWERS[0],
    target_type: "evidence_item",
    old_status: "corrected",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Correction verified against gnomAD v4.1; classification maintained (Likely pathogenic)",
    created_at: "2026-07-29T02:10:00Z",
  },

  // ── Latest batch 2026-07-30 ─────────────────────────────────────────
  extractionEvent("1b2c3d4e-5f60-4771-ff8c-718293a4b5c6", "ce-0015-TTR-pathogenic", "45678901", "2026-07-30T01:45:00Z"),
  {
    review_event_id: "2c3d4e5f-6071-4882-009d-8293a4b5c6d7",
    canonical_evidence_id: "ce-0015-TTR-pathogenic",
    reviewer_id: REVIEWERS[1],
    target_type: "evidence_item",
    old_status: "provisional",
    new_status: "approved",
    field_deltas: [],
    change_reason: "Well-characterized ATTRv allele (p.Val50Met); extraction matches source abstract",
    created_at: "2026-07-30T02:10:00Z",
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

  const effectiveEvents = useMemo(() => {
    if (!events || events.length === 0) return SAMPLE_EVENTS;
    // Demo fallback: when every fetched event is bare (no reviewer, reason,
    // or field deltas — e.g. pipeline auto-approvals), show the curated
    // demo trail so the page remains illustrative. Real curation content
    // always wins.
    const allBare = events.every(
      (e) => !e.reviewer_id && !e.change_reason && e.field_deltas.length === 0,
    );
    return allBare ? SAMPLE_EVENTS : events;
  }, [events]);

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
      {/* Filters */}
      <section
        style={{
          borderRadius: 12,
          border: "1px solid var(--color-primary-300)",
          borderLeft: "4px solid var(--color-primary-600)",
          backgroundColor: "var(--color-surface)",
          boxShadow: "0 8px 24px rgba(8, 145, 178, 0.08)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "16px 18px 0",
            color: "var(--color-text-strong)",
            fontSize: 18,
            fontWeight: 700,
          }}
        >
          {t("audit.filters.title")}
        </div>

        <Flex
          gap={12}
          align="center"
          wrap="wrap"
          justify="space-between"
          style={{ padding: "14px 18px 16px" }}
        >
          <Flex gap={12} align="center" wrap="wrap" style={{ flex: 1, minWidth: 320 }}>
            <Segmented
              size="large"
              value={statusFilter}
              onChange={(val) => setStatusFilter(val as StatusFilter)}
              options={STATUS_FILTERS}
            />
            <Input
              size="large"
              placeholder={t("audit.searchPh")}
              prefix={<Search style={{ width: 16, height: 16, color: "var(--color-text-muted)" }} />}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ flex: "1 1 320px", maxWidth: 460, minWidth: 260 }}
              allowClear
            />
            {filtered.length < effectiveEvents.length && (
              <Typography.Text type="secondary" style={{ fontSize: 13, fontWeight: 500 }}>
                {t("audit.showing", { count: filtered.length, total: effectiveEvents.length })}
              </Typography.Text>
            )}
          </Flex>
          <Button
            size="large"
            icon={<ClipboardCheck style={{ width: 16, height: 16 }} />}
            onClick={() => setReviewDrawerOpen(true)}
          >
            {t("audit.reviewEvidence")}
          </Button>
        </Flex>
      </section>

      {/* Summary stats */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: 0,
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          backgroundColor: "var(--color-bg)",
          padding: "8px 10px",
        }}
      >
        {[
          { label: t("audit.metric.total"), value: stats.total },
          { label: t("audit.metric.approved"), value: stats.approved },
          { label: t("audit.metric.corrected"), value: stats.corrected },
          { label: t("audit.metric.rejected"), value: stats.rejected },
        ].map((item, index) => (
          <div
            key={item.label}
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              gap: 10,
              padding: "6px 10px",
              borderRight: index < 3 ? "1px solid var(--color-border)" : "none",
            }}
          >
            <span style={{ color: "var(--color-text-secondary)", fontSize: 12, fontWeight: 500 }}>
              {item.label}
            </span>
            <span
              style={{
                color: "var(--color-text-secondary)",
                fontFamily: "var(--font-mono)",
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              {item.value}
            </span>
          </div>
        ))}
      </section>

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
