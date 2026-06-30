import { useState } from "react";
import { FileUp, Search, Plus } from "lucide-react";
import {
  App,
  Button,
  Input,
  Modal,
  Segmented,
  Space,
  Tabs,
  Typography,
  Upload,
} from "antd";
import type { TabsProps } from "antd";
import { PageHeader } from "@/components/layout/PageHeader";
import { useI18n } from "@/lib/i18n";
import { RunHistory } from "@/features/pipeline";
import { startPipelineRun } from "@/features/pipeline/services/pipeline";
import type { ProcessingStatus } from "@/lib/types/common";

type FilterValue = "all" | ProcessingStatus;
interface FilterTab {
  value: FilterValue;
  label: string;
}

export function PipelinePage() {
  const [filter, setFilter] = useState<FilterValue>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const { message } = App.useApp();
  const { t } = useI18n();

  const FILTER_TABS: FilterTab[] = [
    { value: "all", label: t("pipeline.filter.all") },
    { value: "running", label: t("pipeline.filter.running") },
    { value: "pending", label: t("pipeline.filter.pending") },
    { value: "completed", label: t("pipeline.filter.completed") },
    { value: "failed", label: t("pipeline.filter.failed") },
  ];
  // ── Upload PDF mode ──
  const [pdfFile, setPdfFile] = useState<File | null>(null);

  // ── Online search mode ──
  const [searchQuery, setSearchQuery] = useState("");
  const [searchIdentifiers, setSearchIdentifiers] = useState("");

  const resetForm = () => {
    setPdfFile(null);
    setSearchQuery("");
    setSearchIdentifiers("");
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      if (pdfFile) {
        // ── Local upload ──
        const base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => {
            const result = reader.result as string;
            const comma = result.indexOf(",");
            resolve(comma >= 0 ? result.slice(comma + 1) : result);
          };
          reader.onerror = () => reject(new Error(t("pipeline.error.readFailed")));
          reader.readAsDataURL(pdfFile);
        });

        await startPipelineRun({
          source_type: "local",
          mode: "full",
          filename: pdfFile.name,
          content_base64: base64,
        });

        void message.success(t("pipeline.success.pdfStarted", { name: pdfFile.name }));
      } else {
        // ── Online search ──
        const trimmedQuery = searchQuery.trim();
        const trimmedIds = searchIdentifiers.trim();
        if (!trimmedQuery && !trimmedIds) {
          void message.warning(t("pipeline.warning.enterQueryOrIds"));
          setSubmitting(false);
          return;
        }

        const ids = trimmedIds
          ? trimmedIds.split(/[,;\s]+/).filter(Boolean)
          : undefined;

        await startPipelineRun({
          source_type: "online",
          mode: "full",
          query: trimmedQuery || undefined,
          identifiers: ids,
        });

        void message.success(
          trimmedQuery
            ? t("pipeline.success.queryStarted", { query: trimmedQuery })
            : t("pipeline.success.idsStarted"),
        );
      }

      setModalOpen(false);
      resetForm();
    } catch (err) {
      const msg = err instanceof Error ? err.message : t("pipeline.error.startFailed");
      void message.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = !!pdfFile || !!searchQuery.trim() || !!searchIdentifiers.trim();

  const tabItems: TabsProps["items"] = [
    {
      key: "upload",
      label: (
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <FileUp size={14} />
          {t("pipeline.upload.title")}
        </span>
      ),
      children: (
        <div style={{ padding: "8px 0" }}>
          <Upload.Dragger
            accept=".pdf"
            maxCount={1}
            beforeUpload={(file) => {
              if (!file.name.toLowerCase().endsWith(".pdf")) {
                void message.error(t("pipeline.error.pdfOnly"));
                return Upload.LIST_IGNORE;
              }
              setPdfFile(file);
              return false; // Prevent auto-upload
            }}
            onRemove={() => setPdfFile(null)}
            fileList={pdfFile ? [{ uid: "-1", name: pdfFile.name, status: "done" as const }] : []}
          >
            <p className="ant-upload-drag-icon">
              <FileUp size={28} style={{ color: "var(--color-text-muted)" }} />
            </p>
            <p className="ant-upload-text" style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
              {t("pipeline.upload.dragText")}
            </p>
          </Upload.Dragger>
        </div>
      ),
    },
    {
      key: "search",
      label: (
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Search size={14} />
          {t("pipeline.search.title")}
        </span>
      ),
      children: (
        <Space direction="vertical" style={{ width: "100%", padding: "8px 0" }} size="middle">
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("pipeline.search.queryPlaceholder")}
            </Typography.Text>
            <Input
              placeholder={t("pipeline.search.queryPlaceholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("pipeline.search.identifiersPlaceholder")}
            </Typography.Text>
            <Input
              placeholder={t("pipeline.search.identifiersPlaceholder")}
              value={searchIdentifiers}
              onChange={(e) => setSearchIdentifiers(e.target.value)}
              style={{ marginTop: 4 }}
            />
          </div>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <PageHeader
        title={t("pipeline.title")}
        description={t("pipeline.description")}
        actions={
          <Button
            type="primary"
            icon={<Plus size={16} />}
            onClick={() => setModalOpen(true)}
          >
            {t("pipeline.newTask")}
          </Button>
        }
      />

      <Segmented
        value={filter}
        onChange={(val) => setFilter(val as FilterValue)}
        options={FILTER_TABS.map((tab) => ({ value: tab.value, label: tab.label }))}
      />

      <RunHistory statusFilter={filter === "all" ? undefined : filter} />

      <Modal
        title={t("pipeline.newTask")}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          resetForm();
        }}
        footer={[
          <Button
            key="cancel"
            onClick={() => {
              setModalOpen(false);
              resetForm();
            }}
          >
            {t("pipeline.cancel")}
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={submitting}
            disabled={!canSubmit}
            onClick={() => void handleSubmit()}
          >
            {t("pipeline.submit")}
          </Button>,
        ]}
        width={500}
        destroyOnHidden
      >
        <Tabs
          items={tabItems}
          onChange={() => resetForm()}
          style={{ marginTop: -8 }}
        />
      </Modal>
    </div>
  );
}
