import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ChevronRight,
  Inbox,
  Layers3,
  ListChecks,
  Radio,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Skeleton } from "@/components/ui/Skeleton";
import { usePipelineRuns } from "../hooks/usePipelineRuns";
import { TaskQueueRow } from "./TaskQueueRow";
import type { PipelineRunSummary } from "../types/pipeline";

interface TaskQueuePanelProps {
  onClose?: () => void;
}

/** Cap the number of recent (terminal) runs rendered to keep the panel light. */
const RECENT_LIMIT = 8;

type TabKey = "active" | "recent";

function isActive(run: PipelineRunSummary): boolean {
  return run.pipeline_status === "running" || run.pipeline_status === "pending";
}

export function TaskQueuePanel({ onClose }: TaskQueuePanelProps) {
  const { data, isLoading, isError, dataUpdatedAt } = usePipelineRuns();
  const [tab, setTab] = useState<TabKey>("active");

  // Memoise the underlying array reference so downstream useMemo callbacks
  // (which depend on `runs`) do not recompute on every render when
  // `data?.items` is undefined and the `?? []` fallback allocates a fresh
  // array. Matches the pattern already used for chat messages.
  const runs = useMemo(() => data?.items ?? [], [data?.items]);
  const { activeRuns, recentRuns } = useMemo(() => {
    const active = runs.filter(isActive);
    // Sort active by started_at desc (newest first); terminal runs likewise.
    const activeSorted = [...active].sort((a, b) => {
      const ta = a.started_at ? new Date(a.started_at).getTime() : 0;
      const tb = b.started_at ? new Date(b.started_at).getTime() : 0;
      return tb - ta;
    });
    const terminal = runs
      .filter((r) => !isActive(r))
      .sort((a, b) => {
        const ta = a.completed_at ?? a.started_at;
        const tb = b.completed_at ?? b.started_at;
        const tA = ta ? new Date(ta).getTime() : 0;
        const tB = tb ? new Date(tb).getTime() : 0;
        return tB - tA;
      })
      .slice(0, RECENT_LIMIT);
    return { activeRuns: activeSorted, recentRuns: terminal };
  }, [runs]);

  const total = data?.total ?? 0;
  const visible = tab === "active" ? activeRuns : recentRuns;
  const emptyMessage =
    tab === "active"
      ? "No active pipelines"
      : "No recent pipelines";

  const updatedAt = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })
    : null;

  return (
    <aside
      className={cn(
        "flex h-full w-80 shrink-0 flex-col border-l border-gray-100 bg-[#fafbfc]",
        "backdrop-blur-sm",
      )}
      aria-label="Task queue"
    >
      {/* Header */}
      <header className="flex items-center gap-2 border-b border-gray-100 px-4 py-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-sm">
          <ListChecks className="h-3.5 w-3.5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[13px] font-semibold tracking-tight text-gray-900">
            Task Queue
          </h2>
          <p className="truncate text-[10.5px] text-gray-500">
            {activeRuns.length > 0 ? (
              <>
                <span className="font-medium text-primary-700">
                  {activeRuns.length}
                </span>{" "}
                active · {total} total
              </>
            ) : (
              <>{total} total pipelines</>
            )}
          </p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close task queue"
            className={cn(
              "rounded-md p-1 text-gray-400 transition-colors",
              "hover:bg-gray-100 hover:text-gray-700",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600",
            )}
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </header>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-3 pt-3">
        <TabButton
          active={tab === "active"}
          onClick={() => setTab("active")}
          icon={<Radio className="h-3 w-3" />}
          label="Active"
          count={activeRuns.length}
          pulse={activeRuns.length > 0}
        />
        <TabButton
          active={tab === "recent"}
          onClick={() => setTab("recent")}
          icon={<Inbox className="h-3 w-3" />}
          label="Recent"
          count={recentRuns.length}
        />
        <Link
          to="/pipeline"
          className={cn(
            "ml-auto flex items-center gap-0.5 rounded-md px-2 py-1 text-[10.5px] font-medium text-gray-500",
            "transition-colors hover:bg-gray-100 hover:text-gray-800",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600",
          )}
          title="Open pipeline page"
        >
          <span>View all</span>
          <ChevronRight className="h-3 w-3" />
        </Link>
      </div>

      {/* Body */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3 pt-2">
        {isLoading && runs.length === 0 ? (
          <LoadingSkeleton />
        ) : isError ? (
          <ErrorState />
        ) : visible.length === 0 ? (
          <EmptyState message={emptyMessage} />
        ) : (
          <ul className="space-y-1">
            {visible.map((run) => (
              <li key={run.processing_run_id}>
                <TaskQueueRow run={run} />
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Footer: last sync indicator */}
      <footer className="flex items-center gap-2 border-t border-gray-100 px-4 py-2 text-[10px] text-gray-400">
        <Activity className="h-3 w-3" aria-hidden />
        <span className="font-mono tabular-nums">
          {updatedAt ? `Synced ${updatedAt}` : "Syncing…"}
        </span>
        <span className="ml-auto flex items-center gap-1">
          <Layers3 className="h-3 w-3" aria-hidden />
          <span>Live</span>
        </span>
      </footer>
    </aside>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  count?: number;
  pulse?: boolean;
}

function TabButton({ active, onClick, icon, label, count, pulse }: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600",
        active
          ? "bg-gray-900 text-white shadow-sm"
          : "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
      )}
    >
      <span className={cn(active ? "text-white" : "text-gray-400")}>{icon}</span>
      <span>{label}</span>
      {typeof count === "number" && count > 0 && (
        <span
          className={cn(
            "min-w-[18px] rounded-full px-1 py-px text-[9.5px] font-semibold tabular-nums",
            active ? "bg-white/20 text-white" : "bg-gray-200 text-gray-700",
          )}
        >
          {count}
        </span>
      )}
      {pulse && !active && (
        <span className="relative ml-0.5 flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary-400 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary-500" />
        </span>
      )}
    </button>
  );
}

function LoadingSkeleton() {
  return (
    <ul className="space-y-2 px-1">
      {Array.from({ length: 3 }).map((_, i) => (
        <li key={i} className="rounded-lg border border-gray-100 bg-white p-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-2.5 w-2.5 rounded-full" />
            <Skeleton className="h-2.5 w-16" />
            <Skeleton className="ml-auto h-3 w-10 rounded-full" />
          </div>
          <Skeleton className="mt-2 h-2 w-3/4" />
          <Skeleton className="mt-2 h-1.5 w-full" />
        </li>
      ))}
    </ul>
  );
}

function ErrorState() {
  return (
    <div className="mx-3 mt-6 rounded-lg border border-red-100 bg-red-50/60 p-4 text-center">
      <p className="text-[11.5px] font-medium text-red-700">
        Unable to load pipelines
      </p>
      <p className="mt-1 text-[10.5px] leading-relaxed text-red-600/80">
        Check the backend connection and try again.
      </p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="mx-3 mt-10 flex flex-col items-center text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-100 text-gray-400">
        <Inbox className="h-4 w-4" aria-hidden />
      </span>
      <p className="mt-3 text-[12px] font-medium text-gray-700">{message}</p>
      <p className="mt-1 max-w-[220px] text-[10.5px] leading-relaxed text-gray-500">
        Pipelines submitted from this chat will appear here in real time.
      </p>
    </div>
  );
}
