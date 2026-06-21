
import { Activity, RefreshCcw } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { RunListItem } from "./RunListItem";
import { usePipelineRuns } from "../hooks/usePipelineRuns";
import { cn } from "@/lib/utils/cn";
import type { ProcessingStatus } from "../types/pipeline";

interface RunHistoryProps {
  className?: string;
  statusFilter?: ProcessingStatus | "all";
}

export function RunHistory({ className, statusFilter }: RunHistoryProps) {
  const { data, isLoading, error, refetch, isFetching } = usePipelineRuns();
  const allItems = data?.items ?? [];
  const items =
    statusFilter && statusFilter !== "all"
      ? allItems.filter((r) => r.pipeline_status === statusFilter)
      : allItems;

  return (
    <section
      className={cn("rounded-xl border border-gray-200 bg-white shadow-sm", className)}
    >
      <header className="flex items-center justify-between border-b border-gray-100 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary-600" aria-hidden />
          <h2 className="text-sm font-semibold tracking-tight text-gray-900">
            Pipeline Runs
          </h2>
          {!isLoading && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 font-mono text-[10px] tabular-nums text-gray-600">
              {items.length}
            </span>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => refetch()}
          loading={isFetching && !isLoading}
          aria-label="Refresh runs"
        >
          <RefreshCcw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </header>

      <div className="p-3">
        {isLoading ? (
          <RunHistorySkeleton />
        ) : error ? (
          <RunHistoryError onRetry={() => refetch()} />
        ) : items.length === 0 ? (
          <RunHistoryEmpty hasFilter={Boolean(statusFilter && statusFilter !== "all")} />
        ) : (
          <ol className="space-y-2">
            {items.map((run, i) => (
              <li key={run.processing_run_id}>
                <RunListItem run={run} index={i} />
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

function RunHistorySkeleton() {
  return (
    <ol className="space-y-2" aria-label="Loading runs">
      {Array.from({ length: 4 }).map((_, i) => (
        <li
          key={i}
          className="rounded-lg border border-gray-200 bg-white p-4"
          style={{ animationDelay: `${i * 60}ms` }}
        >
          <div className="flex items-start gap-3">
            <Skeleton variant="circle" className="mt-1 h-2.5 w-2.5" />
            <div className="flex-1 space-y-2">
              <div className="flex items-center justify-between">
                <Skeleton width="w-48" height="h-3" />
                <Skeleton variant="pill" width="w-16" />
              </div>
              <Skeleton width="w-64" height="h-2" />
              <Skeleton width="w-full" height="h-1" />
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function RunHistoryEmpty({ hasFilter }: { hasFilter: boolean }) {
  return (
    <div className="grid place-items-center px-6 py-10 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-50 text-primary-600">
        <Activity className="h-5 w-5" aria-hidden />
      </div>
      {hasFilter ? (
        <>
          <p className="mt-3 text-sm font-medium text-gray-900">
            No matching runs
          </p>
          <p className="mt-1 max-w-sm text-xs text-gray-500">
            No pipeline runs match the selected filter. Try a different status
            or clear the filter.
          </p>
        </>
      ) : (
        <>
          <p className="mt-3 text-sm font-medium text-gray-900">No runs yet</p>
          <p className="mt-1 max-w-sm text-xs text-gray-500">
            Start a conversation in{" "}
            <Link to="/chat" className="font-medium text-primary-600 hover:underline">
              AI Chat
            </Link>{" "}
            to submit your first pipeline run. Every run will appear here with
            live status.
          </p>
        </>
      )}
    </div>
  );
}

function RunHistoryError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="grid place-items-center px-6 py-10 text-center">
      <p className="text-sm text-red-700">Failed to load runs.</p>
      <p className="mt-1 max-w-sm text-xs text-gray-500">
        We could not reach the pipeline service. Check the connection indicator
        at the top right and try again.
      </p>
      <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
        <RefreshCcw className="h-3.5 w-3.5" />
        Retry
      </Button>
    </div>
  );
}
