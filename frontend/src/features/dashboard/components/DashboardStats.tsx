"use client";

import { FileText, PlayCircle, ClipboardCheck, TrendingUp } from "lucide-react";
import { Spinner } from "@/components/ui/Spinner";
import { Badge } from "@/components/ui/Badge";
import { useDashboard } from "../hooks/useDashboard";

const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "error"> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

export function DashboardStats() {
  const { summary, isLoading, isError, error } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Failed to load dashboard: {error?.message ?? "Unknown error"}
      </div>
    );
  }

  if (!summary) return null;

  const stats = [
    {
      label: "Documents",
      value: summary.total_documents,
      icon: FileText,
      color: "text-blue-600",
    },
    {
      label: "Processing Runs",
      value: summary.total_processing_runs,
      icon: PlayCircle,
      color: "text-purple-600",
    },
    {
      label: "Evidence Items",
      value: summary.total_evidence_items,
      icon: ClipboardCheck,
      color: "text-green-600",
    },
    {
      label: "Avg Confidence",
      value:
        summary.avg_confidence != null
          ? `${(summary.avg_confidence * 100).toFixed(1)}%`
          : "—",
      icon: TrendingUp,
      color: "text-amber-600",
    },
  ];

  const statusEntries = [
    { key: "approved", label: "Approved", count: summary.evidence_by_status.approved },
    { key: "provisional", label: "Provisional", count: summary.evidence_by_status.provisional },
    { key: "corrected", label: "Corrected", count: summary.evidence_by_status.corrected },
    { key: "rejected", label: "Rejected", count: summary.evidence_by_status.rejected },
  ];

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border border-gray-200 bg-white p-4"
          >
            <div className="flex items-center gap-2 text-xs font-medium text-gray-500">
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
              {stat.label}
            </div>
            <p className="mt-2 text-2xl font-semibold text-gray-900">
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      {/* Evidence by status */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-medium text-gray-700">Evidence Review Status</h3>
        <div className="mt-3 flex flex-wrap gap-3">
          {statusEntries.map((entry) => (
            <div key={entry.key} className="flex items-center gap-2">
              <Badge variant={STATUS_VARIANT[entry.key] ?? "default"}>
                {entry.label}
              </Badge>
              <span className="text-sm font-medium text-gray-900">
                {entry.count}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent runs */}
      {summary.recent_runs.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-4 py-3">
            <h3 className="text-sm font-medium text-gray-700">Recent Runs</h3>
          </div>
          <div className="divide-y divide-gray-100">
            {summary.recent_runs.map((run) => (
              <div
                key={run.processing_run_id}
                className="flex items-center justify-between px-4 py-3 text-sm"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-gray-400">
                    {run.processing_run_id.slice(0, 8)}
                  </span>
                  <Badge
                    variant={
                      run.run_status === "completed"
                        ? "success"
                        : run.run_status === "failed"
                          ? "error"
                          : "default"
                    }
                  >
                    {run.run_status}
                  </Badge>
                </div>
                <span className="text-xs text-gray-500">
                  {run.created_at
                    ? new Date(run.created_at).toLocaleString()
                    : "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
