import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Drawer,
  Input,
  Button,
  Select,
  App,
  Typography,
  Spin,
  Empty,
  Tag,
} from "antd";
import { Search, ArrowLeft, CheckCircle2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import { searchEvidence, getEvidenceGroupDetail } from "@/features/evidence-search/services/evidenceSearch";
import { patchEvidence } from "@/features/evidence-search/services/evidenceCorrection";
import type {
  EvidenceSearchResult,
  ReviewStatusValue,
} from "@/features/evidence-search/types/evidenceSearch";
import { buildReviewPatchOperations, cardFieldForFieldId } from "../utils/reviewPatch";

interface EvidenceReviewDrawerProps {
  open: boolean;
  onClose: () => void;
}

const STATUS_BADGE: Record<string, "default" | "success" | "warning" | "error"> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

export function EvidenceReviewDrawer({ open, onClose }: EvidenceReviewDrawerProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { message } = App.useApp();

  const STATUS_OPTIONS: { label: string; value: ReviewStatusValue }[] = [
    { label: t("audit.review.status.approved"), value: "approved" },
    { label: t("audit.review.status.corrected"), value: "corrected" },
    { label: t("audit.review.status.rejected"), value: "rejected" },
  ];

  // Search state
  const [gene, setGene] = useState("");
  const [variant, setVariant] = useState("");
  const [disease, setDisease] = useState("");
  const [searchTriggered, setSearchTriggered] = useState(false);

  // Auto-load all evidence when drawer opens
  useEffect(() => {
    if (open) setSearchTriggered(true);
  }, [open]);

  // Selected item state
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [selectedSourceDocId, setSelectedSourceDocId] = useState<string | null>(null);

  // Search query
  const { data: searchResults, isFetching: isSearching } = useQuery({
    queryKey: ["audit", "evidence-search", gene, variant, disease],
    queryFn: () =>
      searchEvidence({
        gene: gene || undefined,
        variant: variant || undefined,
        disease: disease || undefined,
        page_size: 50,
      }),
    enabled: searchTriggered && open,
    staleTime: 10_000,
  });

  // Detail query for selected item
  const { data: detail, isFetching: isDetailLoading } = useQuery({
    queryKey: ["audit", "evidence-detail", selectedGroupId, selectedSourceDocId],
    queryFn: () =>
      getEvidenceGroupDetail(selectedGroupId!, selectedSourceDocId ?? undefined),
    enabled: !!selectedGroupId && open,
    staleTime: 10_000,
  });

  // Edit state for the selected evidence
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});
  const [newStatus, setNewStatus] = useState<ReviewStatusValue>("approved");
  const [changeReason, setChangeReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSearch = useCallback(() => {
    setSelectedGroupId(null);
    setSelectedSourceDocId(null);
    setSearchTriggered(true);
  }, []);

  const handleSelectItem = useCallback((item: EvidenceSearchResult) => {
    setSelectedGroupId(item.group_id);
    setSelectedSourceDocId(item.source_document_id);
    setEditedFields({});
    setNewStatus("approved");
    setChangeReason("");
  }, []);

  const handleFieldChange = useCallback((fieldName: string, value: string) => {
    setEditedFields((prev) => ({ ...prev, [fieldName]: value }));
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!detail || !detail.items.length) return;

    setIsSubmitting(true);
    try {
      const operations = buildReviewPatchOperations({
        items: detail.items,
        editedFields,
        newStatus,
        changeReason,
      });

      const results = await Promise.all(
        operations.map((operation) =>
          patchEvidence(operation.canonicalEvidenceId, operation.body),
        ),
      );

      const totalDeltas = results.reduce((sum, r) => sum + r.deltas, 0);
      message.success(
        `Reviewed ${results.length} item(s), ${totalDeltas} field change(s) recorded.`,
      );

      // Refresh audit events
      queryClient.invalidateQueries({ queryKey: ["audit", "events"] });

      // Reset
      setSelectedGroupId(null);
      setSelectedSourceDocId(null);
      setEditedFields({});
      setChangeReason("");
      setSearchTriggered(false);
      onClose();
    } catch (err) {
      message.error(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setIsSubmitting(false);
    }
  }, [detail, editedFields, changeReason, newStatus, message, onClose, queryClient]);

  const handleClose = useCallback(() => {
    setSelectedGroupId(null);
    setSelectedSourceDocId(null);
    setSearchTriggered(false);
    setEditedFields({});
    setChangeReason("");
    onClose();
  }, [onClose]);

  const hasFieldEdits = useMemo(
    () => Object.values(editedFields).some((v) => v.trim()),
    [editedFields],
  );
  const canSubmit = useMemo(
    () =>
      hasFieldEdits ||
      (detail?.items.some((item) => item.review_status !== newStatus) ?? false),
    [detail?.items, hasFieldEdits, newStatus],
  );

  return (
    <Drawer
      title={t("audit.review.title")}
      open={open}
      onClose={handleClose}
      styles={{ body: { padding: 0 }, wrapper: { width: 560 } }}
    >
      {/* Search panel — always visible when no item is selected */}
      {!selectedGroupId && (
        <div style={{ padding: "16px 24px" }}>
          <Typography.Text style={{ fontSize: 13, color: "var(--color-text-secondary)", display: "block", marginBottom: 12 }}>
            {t("audit.review.instruction")}
          </Typography.Text>

          <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr 1fr" }}>
            <Input
              placeholder={t("audit.review.genePh")}
              value={gene}
              onChange={(e) => setGene(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
            <Input
              placeholder={t("audit.review.variantPh")}
              value={variant}
              onChange={(e) => setVariant(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
            <Input
              placeholder={t("audit.review.diseasePh")}
              value={disease}
              onChange={(e) => setDisease(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
          </div>

          <Button
            aria-label={t("audit.review.searchBtn")}
            icon={<Search style={{ width: 14, height: 14 }} />}
            onClick={handleSearch}
            loading={isSearching}
            style={{ marginTop: 10, width: "100%" }}
          >
            {t("audit.review.searchBtn")}
          </Button>

          {/* Search results */}
          <div style={{ marginTop: 16 }}>
            {isSearching ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 32 }}>
                <Spin />
              </div>
            ) : searchResults && searchResults.items.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {t("audit.review.resultsFound", { count: searchResults.total })}
                </Typography.Text>
                {searchResults.items.map((item) => (
                  <button
                    key={`${item.group_id}::${item.source_document_id}`}
                    type="button"
                    onClick={() => handleSelectItem(item)}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                      padding: "10px 14px",
                      borderRadius: 8,
                      border: "1px solid var(--color-border)",
                      backgroundColor: "var(--color-surface)",
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "border-color 150ms, box-shadow 150ms",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--color-primary-400)";
                      e.currentTarget.style.boxShadow = "0 2px 8px rgba(8, 145, 178, 0.1)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--color-border)";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <Typography.Text strong style={{ fontSize: 13 }}>
                        {item.gene ?? "—"}
                        {item.variant ? ` / ${item.variant}` : ""}
                      </Typography.Text>
                      <Badge variant={STATUS_BADGE[item.review_status] ?? "default"}>
                        {item.review_status}
                      </Badge>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {item.disease && (
                        <Tag style={{ fontSize: 11, margin: 0 }}>{item.disease}</Tag>
                      )}
                      {item.classification && (
                        <Tag style={{ fontSize: 11, margin: 0 }}>{item.classification}</Tag>
                      )}
                      {item.pmid && (
                        <Tag style={{ fontSize: 11, margin: 0 }}>PMID:{item.pmid}</Tag>
                      )}
                      <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                        {item.field_count} field(s) · avg {((item.avg_confidence ?? 0) * 100).toFixed(0)}%
                      </Typography.Text>
                    </div>
                  </button>
                ))}
              </div>
            ) : searchTriggered ? (
              <Empty
                description={t("audit.review.noResults")}
                style={{ padding: "32px 0" }}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ) : null}
          </div>
        </div>
      )}

      {/* Review panel — shown when an item is selected */}
      {selectedGroupId && (
        <div style={{ padding: "16px 24px" }}>
          {/* Back button */}
          <button
            type="button"
            onClick={() => {
              setSelectedGroupId(null);
              setSelectedSourceDocId(null);
              setEditedFields({});
            }}
            className="edb-back-link"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: "var(--color-text-secondary)",
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 0,
              marginBottom: 16,
              transition: "color 150ms",
            }}
          >
            <ArrowLeft style={{ width: 14, height: 14 }} />
            {t("audit.review.backToResults")}
          </button>

          {isDetailLoading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
              <Spin />
            </div>
          ) : detail ? (
            <>
              {/* Header summary */}
              <div
                style={{
                  borderRadius: 8,
                  border: "1px solid var(--color-border)",
                  padding: "12px 16px",
                  marginBottom: 16,
                  backgroundColor: "var(--color-bg)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <Typography.Text strong style={{ fontSize: 14 }}>
                    {detail.gene ?? "—"}{detail.variant ? ` / ${detail.variant}` : ""}
                  </Typography.Text>
                  <Badge variant={STATUS_BADGE[detail.items[0]?.review_status] ?? "default"}>
                    {detail.items[0]?.review_status ?? "unknown"}
                  </Badge>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {detail.disease && <Tag style={{ fontSize: 11, margin: 0 }}>{detail.disease}</Tag>}
                  {detail.classification && <Tag style={{ fontSize: 11, margin: 0 }}>{detail.classification}</Tag>}
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                    {detail.item_count} field(s) · group {detail.group_id.slice(0, 8)}…
                  </Typography.Text>
                </div>
              </div>

              {/* Editable fields */}
              <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
                {t("audit.review.evidenceFields")}
              </Typography.Text>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
                {detail.items.map((item) => {
                  const fieldKey = item.field_name ?? item.field_id;
                  const edited = editedFields[item.field_id] ?? "";
                  const changed = edited.trim() && edited !== (item.value ?? "");
                  const cardField = cardFieldForFieldId(item.field_id);
                  return (
                    <div
                      key={item.field_id}
                      style={{
                        borderRadius: 8,
                        border: `1px solid ${changed ? "var(--color-highlight-amber-border)" : "var(--color-border)"}`,
                        padding: "10px 14px",
                        backgroundColor: changed ? "var(--color-highlight-amber)" : "var(--color-surface)",
                        transition: "border-color 150ms, background-color 150ms",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <Typography.Text
                            strong
                            style={{
                              fontSize: 12,
                              fontFamily: "var(--font-mono)",
                              color: "var(--color-primary-700)",
                            }}
                          >
                            {fieldKey}
                          </Typography.Text>
                          {item.category && (
                            <Tag style={{ fontSize: 10, margin: 0, lineHeight: "16px", padding: "0 4px" }}>
                              {item.category}
                            </Tag>
                          )}
                        </div>
                        <Badge variant={STATUS_BADGE[item.review_status] ?? "default"}>
                          {item.review_status}
                        </Badge>
                      </div>

                      {/* Current value */}
                      <Typography.Text
                        style={{ fontSize: 12, color: "var(--color-text-strong)", display: "block", marginBottom: 6 }}
                      >
                        {item.value || <span style={{ color: "var(--color-text-muted)" }}>{t("audit.review.emptyValue")}</span>}
                      </Typography.Text>

                      {/* Edit input */}
                      <Input
                        size="small"
                        placeholder={
                          cardField
                            ? t("audit.review.correctedPh", { field: cardField })
                            : t("audit.review.statusOnlyPh")
                        }
                        value={edited}
                        onChange={(e) => handleFieldChange(item.field_id, e.target.value)}
                        disabled={!cardField}
                        style={{
                          borderColor: changed ? "var(--color-highlight-amber-border)" : undefined,
                        }}
                      />
                      {changed && (
                        <Typography.Text style={{ fontSize: 10, color: "var(--color-warning-text)", marginTop: 4, display: "block" }}>
                          {t("audit.review.willUpdate")}
                        </Typography.Text>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Status + reason + submit */}
              <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr", marginBottom: 12 }}>
                <div>
                  <Typography.Text style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-strong)", display: "block", marginBottom: 4 }}>
                    {t("audit.review.newStatus")}
                  </Typography.Text>
                  <Select
                    aria-label={t("audit.review.newStatus")}
                    value={newStatus}
                    onChange={(val) => setNewStatus(val as ReviewStatusValue)}
                    options={STATUS_OPTIONS}
                    style={{ width: "100%" }}
                    size="small"
                  />
                </div>
                <div>
                  <Typography.Text style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-strong)", display: "block", marginBottom: 4 }}>
                    {t("audit.review.reason")}
                  </Typography.Text>
                  <Input
                    size="small"
                    placeholder={t("audit.review.reasonPh")}
                    value={changeReason}
                    onChange={(e) => setChangeReason(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <Button
                  type="primary"
                  icon={<CheckCircle2 style={{ width: 14, height: 14 }} />}
                  onClick={handleSubmit}
                  loading={isSubmitting}
                  disabled={!canSubmit}
                >
                  {t("audit.review.submit")}
                </Button>
                <Button
                  icon={<X style={{ width: 14, height: 14 }} />}
                  onClick={() => {
                    setSelectedGroupId(null);
                    setEditedFields({});
                  }}
                  disabled={isSubmitting}
                >
                  {t("audit.review.cancelBtn")}
                </Button>
              </div>

              {hasFieldEdits && (
                <Typography.Text style={{ fontSize: 11, color: "var(--color-text-secondary)", marginTop: 8, display: "block" }}>
                  {t("audit.review.auditNotice", { count: Object.values(editedFields).filter((v) => v.trim()).length })}
                </Typography.Text>
              )}
            </>
          ) : null}
        </div>
      )}
    </Drawer>
  );
}
