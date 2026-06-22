import { Activity, RefreshCcw } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { RunListItem } from "./RunListItem";
import { usePipelineRuns } from "../hooks/usePipelineRuns";
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
      className={className}
      style={{
        borderRadius: 12,
        border: "1px solid #e5e7eb",
        backgroundColor: "#fff",
        boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
      }}
    >
      <header style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid #f3f4f6",
        padding: "14px 20px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Activity style={{ width: 16, height: 16, color: "var(--color-primary-600)" }} aria-hidden />
          <h2 style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em", color: "#111827", margin: 0 }}>
            Pipeline Runs
          </h2>
          {!isLoading && (
            <span style={{
              borderRadius: 9999,
              backgroundColor: "#f3f4f6",
              padding: "2px 8px",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              fontVariantNumeric: "tabular-nums",
              color: "#4b5563",
            }}>
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
          <RefreshCcw style={{ width: 14, height: 14 }} />
          Refresh
        </Button>
      </header>

      <div style={{ padding: 12 }}>
        {isLoading ? (
          <RunHistorySkeleton />
        ) : error ? (
          <RunHistoryError onRetry={() => refetch()} />
        ) : items.length === 0 ? (
          <RunHistoryEmpty hasFilter={Boolean(statusFilter && statusFilter !== "all")} />
        ) : (
          <ol className="content-fade-in" style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
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
    <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }} aria-label="Loading runs">
      {Array.from({ length: 4 }).map((_, i) => (
        <li
          key={i}
          style={{
            borderRadius: 8,
            border: "1px solid #e5e7eb",
            backgroundColor: "#fff",
            padding: 16,
            animationDelay: `${i * 60}ms`,
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <Skeleton variant="circle" style={{ marginTop: 4, width: 10, height: 10 }} />
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <Skeleton style={{ width: 192, height: 12 }} />
                <Skeleton variant="pill" style={{ width: 64 }} />
              </div>
              <Skeleton style={{ width: 256, height: 8 }} />
              <Skeleton style={{ width: "100%", height: 4 }} />
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function RunHistoryEmpty({ hasFilter }: { hasFilter: boolean }) {
  return (
    <div style={{
      display: "grid",
      placeItems: "center",
      padding: "40px 24px",
      textAlign: "center",
    }}>
      <div style={{
        display: "flex",
        width: 40,
        height: 40,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "50%",
        backgroundColor: "var(--color-primary-50)",
        color: "var(--color-primary-600)",
      }}>
        <Activity style={{ width: 20, height: 20 }} aria-hidden />
      </div>
      {hasFilter ? (
        <>
          <p style={{ marginTop: 12, fontSize: 14, fontWeight: 500, color: "#111827" }}>
            No matching runs
          </p>
          <p style={{ marginTop: 4, maxWidth: 384, fontSize: 12, color: "#6b7280" }}>
            No pipeline runs match the selected filter. Try a different status
            or clear the filter.
          </p>
        </>
      ) : (
        <>
          <p style={{ marginTop: 12, fontSize: 14, fontWeight: 500, color: "#111827" }}>No runs yet</p>
          <p style={{ marginTop: 4, maxWidth: 384, fontSize: 12, color: "#6b7280" }}>
            Start a conversation in{" "}
            <Link to="/chat" style={{ fontWeight: 500, color: "var(--color-primary-600)" }}>
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
    <div style={{
      display: "grid",
      placeItems: "center",
      padding: "40px 24px",
      textAlign: "center",
    }}>
      <p style={{ fontSize: 14, color: "#b91c1c", margin: 0 }}>Failed to load runs.</p>
      <p style={{ marginTop: 4, maxWidth: 384, fontSize: 12, color: "#6b7280" }}>
        We could not reach the pipeline service. Check the connection indicator
        at the top right and try again.
      </p>
      <Button variant="secondary" size="sm" style={{ marginTop: 12 }} onClick={onRetry}>
        <RefreshCcw style={{ width: 14, height: 14 }} />
        Retry
      </Button>
    </div>
  );
}
