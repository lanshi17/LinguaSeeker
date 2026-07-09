import { useState, useMemo, useCallback } from "react";
import { useI18n } from "@/lib/i18n";
import { Drawer, Button, Slider, Checkbox, Select, Tag, message, Tooltip } from "antd";
import {
  Download,
  FileText,
  FileJson,
  FileSpreadsheet,
  File,
  Eye,
  Settings2,
  Check,
} from "lucide-react";
import type {
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
} from "../types/evidenceSearch";
import {
  REPORT_FORMATS,
  DEFAULT_EXPORT_OPTIONS,
  exportEvidenceReport,
  buildPreview,
  countFilteredItems,
} from "../utils/evidenceReport";
import type { ReportFormat, ExportOptions } from "../utils/evidenceReport";
import { CATEGORY_COLORS } from "../utils/evidenceDocument";
import { categoryLabel } from "../utils/categoryStyles";

/* ── Constants ────────────────────────────────────────────────────── */

const FORMAT_ICONS: Record<ReportFormat, React.ComponentType<{ style?: React.CSSProperties }>> = {
  markdown: FileText,
  json: FileJson,
  csv: FileSpreadsheet,
  pdf: File,
};

const STATUS_OPTIONS = ["provisional", "approved", "corrected", "rejected"];

/* ── Helpers ──────────────────────────────────────────────────────── */

function categoryFromItem(item: EvidenceGroupItem): string | null {
  if (item.category) return item.category;
  return item.field_id.includes(".") ? item.field_id.split(".", 1)[0] : null;
}

/* ── Component ────────────────────────────────────────────────────── */

interface ExportReportDrawerProps {
  detail: EvidenceGroupDetailResponse;
  open: boolean;
  onClose: () => void;
}

export function ExportReportDrawer({ detail, open, onClose }: ExportReportDrawerProps) {
  const [selectedFormat, setSelectedFormat] = useState<ReportFormat>("markdown");
  const [options, setOptions] = useState<ExportOptions>({ ...DEFAULT_EXPORT_OPTIONS });
  const [showPreview, setShowPreview] = useState(false);
  const [exporting, setExporting] = useState(false);
  const { t } = useI18n();

  // Available categories derived from the actual items.
  const availableCategories = useMemo(() => {
    const cats = new Set<string>();
    for (const item of detail.items) {
      const cat = categoryFromItem(item);
      if (cat) cats.add(cat);
    }
    return [...cats].sort();
  }, [detail.items]);

  const filteredCount = useMemo(() => countFilteredItems(detail, options), [detail, options]);

  const preview = useMemo(() => {
    if (!showPreview) return "";
    return buildPreview(detail, selectedFormat, options);
  }, [detail, selectedFormat, options, showPreview]);

  const updateOpts = useCallback(
    (patch: Partial<ExportOptions>) => setOptions((prev) => ({ ...prev, ...patch })),
    [],
  );

  const handleExport = useCallback(() => {
    setExporting(true);
    try {
      exportEvidenceReport(detail, selectedFormat, options);
      void message.success(t("evidence.export.success"));
    } catch {
      void message.error(t("evidence.export.error"));
    } finally {
      setExporting(false);
    }
  }, [detail, selectedFormat, options, t]);

  const FormatIcon = FORMAT_ICONS[selectedFormat];

  return (
    <Drawer
      title={
        <span style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 16, fontWeight: 600 }}>
          <Download style={{ width: 20, height: 20, color: "var(--color-primary-600, var(--color-primary-600))" }} />
          {t("evidence.export.title")}
        </span>
      }
      open={open}
      onClose={onClose}
      styles={{ body: { padding: "16px 24px" }, wrapper: { width: 480 } }}
      extra={
        <Button
          type="primary"
          icon={<Download style={{ width: 16, height: 16 }} />}
          loading={exporting}
          onClick={handleExport}
          disabled={filteredCount === 0}
        >
          {t("evidence.export.btn", { count: filteredCount })}
        </Button>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* ── Format selector ── */}
        <section>
          <h3
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--color-text-secondary)",
              margin: "0 0 12px",
            }}
          >
            <File style={{ width: 14, height: 14 }} />
            {t("evidence.export.format")}
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
            {REPORT_FORMATS.map((f) => {
              const Icon = FORMAT_ICONS[f.format];
              const active = selectedFormat === f.format;
              return (
                <button
                  key={f.format}
                  type="button"
                  onClick={() => setSelectedFormat(f.format)}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                    padding: "12px 14px",
                    borderRadius: 8,
                    border: `1.5px solid ${active ? "var(--color-primary-400, var(--color-primary-400))" : "var(--color-border)"}`,
                    backgroundColor: active ? "var(--color-primary-50, var(--color-primary-50))" : "var(--color-surface)",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 150ms",
                  }}
                >
                  <Icon
                    style={{
                      width: 18,
                      height: 18,
                      flexShrink: 0,
                      marginTop: 1,
                      color: active
                        ? "var(--color-primary-600, var(--color-primary-600))"
                        : "var(--color-text-muted)",
                    }}
                  />
                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 14,
                        fontWeight: 600,
                        color: active ? "var(--color-primary-800, var(--color-primary-800))" : "var(--color-text)",
                      }}
                    >
                      {f.label}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 2 }}>
                      {f.description}
                    </div>
                  </div>
                  {active && (
                    <Check
                      style={{
                        width: 16,
                        height: 16,
                        flexShrink: 0,
                        marginLeft: "auto",
                        color: "var(--color-primary-600, var(--color-primary-600))",
                      }}
                    />
                  )}
                </button>
              );
            })}
          </div>
        </section>

        {/* ── Export options ── */}
        <section>
          <h3
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--color-text-secondary)",
              margin: "0 0 12px",
            }}
          >
            <Settings2 style={{ width: 14, height: 14 }} />
            {t("evidence.export.options")}
          </h3>

          <div
            style={{
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
            }}
          >
            {/* Include traces */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 16px",
                borderBottom: "1px solid var(--color-bg-muted)",
                cursor: "pointer",
                fontSize: 14,
                color: "var(--color-text-strong)",
              }}
            >
              <span>{t("evidence.export.includeTraces")}</span>
              <Checkbox
                checked={options.includeTraces}
                onChange={(e) => updateOpts({ includeTraces: e.target.checked })}
              />
            </label>

            {/* Include bilingual text */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 16px",
                borderBottom: "1px solid var(--color-bg-muted)",
                cursor: "pointer",
                fontSize: 14,
                color: "var(--color-text-strong)",
              }}
            >
              <span>{t("evidence.export.includeFullText")}</span>
              <Checkbox
                checked={options.includeBilingualText}
                onChange={(e) => updateOpts({ includeBilingualText: e.target.checked })}
              />
            </label>

            {/* Confidence threshold */}
            <div
              style={{
                padding: "12px 16px",
                borderBottom: "1px solid var(--color-bg-muted)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 8,
                  fontSize: 14,
                  color: "var(--color-text-strong)",
                }}
              >
                <span>{t("evidence.export.minConfidence")}</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono, monospace)",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--color-primary-700, var(--color-primary-700))",
                  }}
                >
                  {(options.confidenceThreshold * 100).toFixed(0)}%
                </span>
              </div>
              <Slider
                min={0}
                max={1}
                step={0.05}
                value={options.confidenceThreshold}
                onChange={(v) => updateOpts({ confidenceThreshold: v })}
                styles={{ track: { backgroundColor: "var(--color-primary-500, #06b6d4)" } }}
                tooltip={{
                  formatter: (v) => `${((v ?? 0) * 100).toFixed(0)}%`,
                }}
              />
            </div>

            {/* Status filter */}
            <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-bg-muted)" }}>
              <div
                style={{
                  fontSize: 14,
                  color: "var(--color-text-strong)",
                  marginBottom: 8,
                }}
              >
                {t("evidence.export.statusFilter")}
              </div>
              <Select
                mode="multiple"
                allowClear
                placeholder={t("evidence.export.allStatuses")}
                value={options.statusFilter.length > 0 ? options.statusFilter : undefined}
                onChange={(v) => updateOpts({ statusFilter: v ?? [] })}
                options={STATUS_OPTIONS.map((s) => ({ label: t(`evidence.export.status.${s}`), value: s }))}
                style={{ width: "100%" }}
                maxTagCount="responsive"
              />
            </div>

            {/* Category filter */}
            <div style={{ padding: "12px 16px" }}>
              <div
                style={{
                  fontSize: 14,
                  color: "var(--color-text-strong)",
                  marginBottom: 8,
                }}
              >
                {t("evidence.export.categoryFilter")}
              </div>
              <Select
                mode="multiple"
                allowClear
                placeholder={t("evidence.export.allCategories")}
                value={options.categoryFilter.length > 0 ? options.categoryFilter : undefined}
                onChange={(v) => updateOpts({ categoryFilter: v ?? [] })}
                options={availableCategories.map((c) => ({
                  label: `${c} — ${categoryLabel(c)}`,
                  value: c,
                }))}
                style={{ width: "100%" }}
                maxTagCount="responsive"
                optionRender={(opt) => {
                  const cat = opt.value as string;
                  const hex = CATEGORY_COLORS[cat]?.hex ?? "var(--color-text-secondary)";
                  return (
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          backgroundColor: hex,
                          flexShrink: 0,
                        }}
                      />
                      {opt.label as string}
                    </span>
                  );
                }}
              />
            </div>
          </div>
        </section>

        {/* ── Summary bar ── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-bg)",
            padding: "10px 16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <FormatIcon
              style={{ width: 16, height: 16, color: "var(--color-primary-600, var(--color-primary-600))" }}
            />
            <span style={{ fontSize: 13, color: "var(--color-text-strong)" }}>
              {t("evidence.export.itemsSummary", { selected: filteredCount, total: detail.item_count })}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {filteredCount < detail.item_count && (
              <Tag
                color="orange"
                style={{ margin: 0, fontSize: 11 }}
              >
                {t("evidence.export.filtered")}
              </Tag>
            )}
            <Tag
              color="cyan"
              style={{ margin: 0, fontSize: 11 }}
            >
              {selectedFormat.toUpperCase()}
            </Tag>
          </div>
        </div>

        {/* ── Preview toggle ── */}
        <div>
          <Button
            block
            icon={<Eye style={{ width: 14, height: 14 }} />}
            onClick={() => setShowPreview((v) => !v)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              height: 40,
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 500,
            }}
          >
            {showPreview ? t("evidence.export.hidePreview") : t("evidence.export.showPreview")}
          </Button>

          {showPreview && (
            <Tooltip title="Preview shows the first portion of the exported content">
              <pre
                style={{
                  marginTop: 12,
                  maxHeight: 320,
                  overflow: "auto",
                  borderRadius: 8,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-bg)",
                  padding: 16,
                  fontSize: 12,
                  lineHeight: "20px",
                  fontFamily: "var(--font-mono, monospace)",
                  color: "var(--color-text-strong)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {preview}
              </pre>
            </Tooltip>
          )}
        </div>
      </div>
    </Drawer>
  );
}
