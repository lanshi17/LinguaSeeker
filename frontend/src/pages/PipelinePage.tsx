import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquarePlus } from "lucide-react";
import { Button, Segmented } from "antd";
import { PageHeader } from "@/components/layout/PageHeader";
import { RunHistory } from "@/features/pipeline";
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
  const navigate = useNavigate();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <PageHeader
        title="Task Management"
        description="Monitor and manage all pipeline runs. Start a new task from AI Chat."
        actions={
          <Button
            type="primary"
            icon={<MessageSquarePlus size={16} />}
            onClick={() => navigate("/chat")}
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
    </div>
  );
}
