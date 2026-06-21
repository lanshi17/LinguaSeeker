import { useState } from "react";
import { Link } from "react-router-dom";
import { MessageSquarePlus } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { RunHistory } from "@/features/pipeline";
import { cn } from "@/lib/utils/cn";
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

  return (
    <div className="space-y-5">
      <PageHeader
        title="Task Management"
        description="Monitor and manage all pipeline runs. Start a new task from AI Chat."
        actions={
          <Link
            to="/chat"
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3.5 py-2 text-sm font-medium text-white",
              "transition-colors hover:bg-primary-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600",
            )}
          >
            <MessageSquarePlus className="h-4 w-4" />
            New Task
          </Link>
        }
      />

      <div className="flex gap-1 overflow-x-auto rounded-lg border border-gray-200 bg-white p-1">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setFilter(tab.value)}
            className={cn(
              "shrink-0 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors",
              filter === tab.value
                ? "bg-primary-50 text-primary-700"
                : "text-gray-500 hover:bg-gray-50 hover:text-gray-700",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <RunHistory statusFilter={filter === "all" ? undefined : filter} />
    </div>
  );
}
