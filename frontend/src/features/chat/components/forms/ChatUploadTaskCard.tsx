import { useCallback, useEffect, useState } from "react";
import { App, Button, Input, Upload } from "antd";
import { CheckCircle2, FileText, Target, Upload as UploadIcon, X } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import type { PipelineSummarySlots } from "./PipelineSummaryCard";
import { isPdfFile } from "./uploadFile";

interface ChatUploadTaskCardProps {
  slots: PipelineSummarySlots;
  initialFile?: File | null;
  isSubmitting?: boolean;
  onCancel?: () => void;
  onSubmit: (slots: PipelineSummarySlots, file: File) => void;
}

interface TargetFieldProps {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
  mono?: boolean;
}

function TargetField({
  label,
  value,
  placeholder,
  onChange,
  mono,
}: TargetFieldProps) {
  return (
    <label style={{ display: "grid", gap: 4 }}>
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--color-text-secondary)",
        }}
      >
        {label}
      </span>
      <Input
        size="small"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        style={{ fontFamily: mono ? "var(--font-mono)" : undefined }}
      />
    </label>
  );
}

export function ChatUploadTaskCard({
  slots,
  initialFile,
  isSubmitting,
  onCancel,
  onSubmit,
}: ChatUploadTaskCardProps) {
  const { t } = useI18n();
  const { message } = App.useApp();
  const [file, setFile] = useState<File | null>(initialFile ?? null);
  const [gene, setGene] = useState(slots.gene_symbol ?? "");
  const [disease, setDisease] = useState(slots.disease_name ?? "");
  const [variant, setVariant] = useState(slots.variant_hgvs_p ?? "");

  useEffect(() => {
    setFile(initialFile ?? null);
  }, [initialFile]);

  useEffect(() => {
    setGene(slots.gene_symbol ?? "");
    setDisease(slots.disease_name ?? "");
    setVariant(slots.variant_hgvs_p ?? "");
  }, [slots.disease_name, slots.gene_symbol, slots.variant_hgvs_p]);

  const handleSubmit = useCallback(() => {
    if (!file) {
      void message.warning(t("chat.upload.fileRequired"));
      return;
    }
    onSubmit(
      {
        ...slots,
        source_type: "local",
        filename: file.name,
        gene_symbol: gene.trim() || undefined,
        disease_name: disease.trim() || undefined,
        variant_hgvs_p: variant.trim() || undefined,
      },
      file,
    );
  }, [disease, file, gene, message, onSubmit, slots, t, variant]);

  return (
    <div
      style={{
        width: "100%",
        maxWidth: 520,
        overflow: "hidden",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        backgroundColor: "var(--color-surface)",
        boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          borderBottom: "1px solid var(--color-bg-muted)",
          padding: "10px 14px",
        }}
      >
        <span
          style={{
            display: "flex",
            width: 28,
            height: 28,
            flexShrink: 0,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 6,
            backgroundColor: "var(--color-highlight-purple)",
            color: "var(--color-purple-700)",
          }}
        >
          <UploadIcon size={15} aria-hidden />
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <h3
            style={{
              margin: 0,
              fontSize: 13,
              fontWeight: 600,
              color: "var(--color-text)",
            }}
          >
            {t("chat.upload.heading")}
          </h3>
          <p
            style={{
              margin: "2px 0 0",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontSize: 12,
              color: "var(--color-text-secondary)",
            }}
          >
            {t("chat.upload.description")}
          </p>
        </div>
        {onCancel ? (
          <Button
            type="text"
            size="small"
            icon={<X size={14} />}
            onClick={onCancel}
            aria-label={t("chat.upload.cancel")}
          />
        ) : null}
      </div>

      <div style={{ display: "grid", gap: 12, padding: 14 }}>
        <Upload.Dragger
          accept="application/pdf,.pdf"
          maxCount={1}
          beforeUpload={(nextFile) => {
            if (!isPdfFile(nextFile)) {
              void message.error(t("pipeline.error.pdfOnly"));
              return Upload.LIST_IGNORE;
            }
            setFile(nextFile);
            return false;
          }}
          fileList={
            file
              ? [{ uid: "-1", name: file.name, status: "done" as const }]
              : []
          }
          onRemove={() => {
            setFile(null);
          }}
        >
          <p className="ant-upload-drag-icon" style={{ marginBottom: 6 }}>
            <FileText size={24} style={{ color: "var(--color-text-muted)" }} />
          </p>
          <p
            className="ant-upload-text"
            style={{ margin: 0, fontSize: 13, color: "var(--color-text)" }}
          >
            {file ? file.name : t("chat.upload.dropText")}
          </p>
        </Upload.Dragger>

        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Target size={13} style={{ color: "var(--color-text-muted)" }} />
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--color-text)",
              }}
            >
              {t("chat.upload.targetHeading")}
            </span>
          </div>
          <div className="chat-upload-target-grid" style={{ display: "grid", gap: 8 }}>
            <TargetField
              label={t("chat.upload.gene")}
              value={gene}
              placeholder="BRCA1"
              onChange={setGene}
              mono
            />
            <TargetField
              label={t("chat.upload.disease")}
              value={disease}
              placeholder="Hereditary breast and ovarian cancer"
              onChange={setDisease}
            />
            <TargetField
              label={t("chat.upload.variant")}
              value={variant}
              placeholder="c.5266dupC"
              onChange={setVariant}
              mono
            />
          </div>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderTop: "1px solid var(--color-bg-muted)",
          padding: "10px 14px",
        }}
      >
        <Button
          type="primary"
          size="small"
          disabled={!file}
          loading={isSubmitting}
          onClick={handleSubmit}
          style={{ minWidth: 150 }}
        >
          <CheckCircle2 size={14} style={{ marginRight: 6 }} />
          {t("chat.upload.submit")}
        </Button>
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            fontSize: 11,
            color: "var(--color-text-muted)",
          }}
        >
          {file ? t("chat.upload.ready") : t("chat.upload.fileRequired")}
        </span>
      </div>
    </div>
  );
}
