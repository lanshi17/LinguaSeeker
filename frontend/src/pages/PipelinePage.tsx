import { useState, useRef } from "react";
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
import { RunHistory } from "@/features/pipeline";
import { startPipelineRun } from "@/features/pipeline/services/pipeline";
import type { ProcessingStatus } from "@/lib/types/common";

type FilterValue = "all" | ProcessingStatus;

interface FilterTab {
  value: FilterValue;
  label: string;
}

const FILTER_TABS: FilterTab[] = [
  { value: "all", label: "All" },
  { value: "running", label: "Running" },
  { value: "pending", label: "Pending" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

export function PipelinePage() {
  const [filter, setFilter] = useState<FilterValue>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const { message } = App.useApp();

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
          reader.onerror = () => reject(new Error("Failed to read file"));
          reader.readAsDataURL(pdfFile);
        });

        await startPipelineRun({
          source_type: "local",
          mode: "full",
          filename: pdfFile.name,
          content_base64: base64,
        });

        void message.success(`"${pdfFile.name}" — pipeline started`);
      } else {
        // ── Online search ──
        const trimmedQuery = searchQuery.trim();
        const trimmedIds = searchIdentifiers.trim();
        if (!trimmedQuery && !trimmedIds) {
          void message.warning("Enter a search query or identifiers (DOI/PMID/PMCID)");
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
            ? `"${trimmedQuery}" — pipeline started`
            : `Search by identifiers — pipeline started`,
        );
      }

      setModalOpen(false);
      resetForm();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start pipeline";
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
          Upload PDF
        </span>
      ),
      children: (
        <div style={{ padding: "8px 0" }}>
          <Upload.Dragger
            accept=".pdf"
            maxCount={1}
            beforeUpload={(file) => {
              if (!file.name.toLowerCase().endsWith(".pdf")) {
                void message.error("Only PDF files are supported");
                return Upload.LIST_IGNORE;
              }
              setPdfFile(file);
              return false; // Prevent auto-upload
            }}
            onRemove={() => setPdfFile(null)}
            fileList={pdfFile ? [{ uid: "-1", name: pdfFile.name, status: "done" as const }] : []}
          >
            <p className="ant-upload-drag-icon">
              <FileUp size={28} style={{ color: "#9ca3af" }} />
            </p>
            <p className="ant-upload-text" style={{ fontSize: 13, color: "#6b7280" }}>
              Click or drag a PDF file here
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
          Online Search
        </span>
      ),
      children: (
        <Space direction="vertical" style={{ width: "100%", padding: "8px 0" }} size="middle">
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Search query
            </Typography.Text>
            <Input
              placeholder="e.g. BRCA1 breast cancer literature"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Identifiers (DOI, PMID, PMCID — comma-separated)
            </Typography.Text>
            <Input
              placeholder="e.g. 10.1038/s41586-020-2222-3, 34521984"
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
        title="Task Management"
        description="Monitor and manage all pipeline runs. Click New Task to upload a PDF or search online."
        actions={
          <Button
            type="primary"
            icon={<Plus size={16} />}
            onClick={() => setModalOpen(true)}
          >
            New Task
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
        title="New Task"
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
            Cancel
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={submitting}
            disabled={!canSubmit}
            onClick={() => void handleSubmit()}
          >
            Start Pipeline
          </Button>,
        ]}
        width={500}
        destroyOnClose
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
