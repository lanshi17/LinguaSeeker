import { useState, useCallback } from "react";
import { Activity, RefreshCcw, Search, X, ChevronLeft, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, Input } from "antd";
import { Skeleton } from "@/components/ui/Skeleton";
import { RunListItem } from "./RunListItem";
import { usePipelineRuns } from "../hooks/usePipelineRuns";
import type { ProcessingStatus } from "../types/pipeline";

const PAGE_SIZE = 20;

/* ── Embedded styles for pagination ────────────────────────── */

const paginationCSS = `
.rh-page-btn:hover {
  background-color: #f9fafb;
}
.rh-page-jump-input {
  width: 48px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  text-align: center;
  font-size: 13px;
  font-family: var(--font-mono);
  color: #374151;
  outline: none;
  transition: border-color 0.15s;
}
.rh-page-jump-input:focus {
  border-color: var(--color-primary-600);
  box-shadow: 0 0 0 2px var(--color-primary-100, rgba(8,145,178,0.15));
}
.rh-page-jump-input::placeholder {
  color: #9ca3af;
}
`;

interface RunHistoryProps {
  className?: string;
  statusFilter?: ProcessingStatus | "all";
}

export function RunHistory({ className, statusFilter }: RunHistoryProps) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [jumpValue, setJumpValue] = useState("");

  const { data, isLoading, error, refetch, isFetching } = usePipelineRuns({
    page,
    pageSize: PAGE_SIZE,
    status: statusFilter && statusFilter !== "all" ? statusFilter : undefined,
    search: search || undefined,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handleJump = useCallback(() => {
    const num = parseInt(jumpValue, 10);
    if (!Number.isNaN(num) && num >= 1 && num <= totalPages) {
      setPage(num);
      setJumpValue("");
    }
  }, [jumpValue, totalPages]);

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

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
      <style>{paginationCSS}</style>
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
              {total}
            </span>
          )}
        </div>
        <Button
          type="text"
          size="small"
          onClick={() => refetch()}
          loading={isFetching && !isLoading}
          aria-label="Refresh runs"
        >
          <RefreshCcw style={{ width: 14, height: 14 }} />
          Refresh
        </Button>
      </header>

      {/* Search bar */}
      <div style={{ padding: "12px 20px 0" }}>
        <Input
          placeholder="Search by title, identifier, or source key..."
          prefix={<Search style={{ width: 14, height: 14, color: "#9ca3af" }} />}
          suffix={
            search ? (
              <button
                type="button"
                onClick={() => handleSearchChange("")}
                style={{
                  cursor: "pointer",
                  border: "none",
                  background: "none",
                  padding: 2,
                  color: "#9ca3af",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <X style={{ width: 14, height: 14 }} />
              </button>
            ) : undefined
          }
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          allowClear={false}
          style={{ borderRadius: 8 }}
        />
      </div>

      <div style={{ padding: 12 }}>
        {isLoading ? (
          <RunHistorySkeleton />
        ) : error ? (
          <RunHistoryError onRetry={() => refetch()} />
        ) : items.length === 0 ? (
          <RunHistoryEmpty hasFilter={Boolean(statusFilter && statusFilter !== "all") || !!search} />
        ) : (
          <>
            <ol className="content-fade-in" style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
              {items.map((run, i) => (
                <li key={run.processing_run_id}>
                  <RunListItem run={run} index={i} />
                </li>
              ))}
            </ol>

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                paddingTop: 16,
                marginTop: 12,
                borderTop: "1px solid #f3f4f6",
              }}>
                <button
                  type="button"
                  onClick={() => setPage(page - 1)}
                  disabled={page <= 1}
                  className={page > 1 ? "rh-page-btn" : undefined}
                  style={{
                    display: "flex",
                    width: 36,
                    height: 36,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 8,
                    border: page <= 1 ? "1px solid #f3f4f6" : "1px solid #e5e7eb",
                    fontSize: 14,
                    color: page <= 1 ? "#d1d5db" : "#4b5563",
                    cursor: page <= 1 ? "not-allowed" : "pointer",
                    backgroundColor: "#fff",
                    transition: "background-color 0.15s",
                  }}
                >
                  <ChevronLeft style={{ width: 16, height: 16 }} />
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  const pageNum = i + 1;
                  const isActive = pageNum === page;
                  return (
                    <button
                      key={pageNum}
                      type="button"
                      onClick={() => setPage(pageNum)}
                      className={!isActive ? "rh-page-btn" : undefined}
                      style={{
                        display: "flex",
                        width: 36,
                        height: 36,
                        alignItems: "center",
                        justifyContent: "center",
                        borderRadius: 8,
                        border: isActive ? "1px solid var(--color-primary-600)" : "1px solid #e5e7eb",
                        fontSize: 14,
                        fontWeight: 500,
                        backgroundColor: isActive ? "var(--color-primary-600)" : "#fff",
                        color: isActive ? "#fff" : "#4b5563",
                        cursor: "pointer",
                        transition: "background-color 0.15s",
                      }}
                    >
                      {pageNum}
                    </button>
                  );
                })}
                {totalPages > 7 && (
                  <>
                    <span style={{ padding: "0 4px", color: "#9ca3af" }}>&hellip;</span>
                    <input
                      className="rh-page-jump-input"
                      type="text"
                      inputMode="numeric"
                      placeholder={String(totalPages)}
                      value={jumpValue}
                      onChange={(e) => {
                        const v = e.target.value.replace(/\D/g, "");
                        setJumpValue(v);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleJump();
                      }}
                      onBlur={handleJump}
                      aria-label="Jump to page"
                      title={`Jump to page (1–${totalPages})`}
                    />
                  </>
                )}
                <button
                  type="button"
                  onClick={() => setPage(page + 1)}
                  disabled={page >= totalPages}
                  className={page < totalPages ? "rh-page-btn" : undefined}
                  style={{
                    display: "flex",
                    width: 36,
                    height: 36,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 8,
                    border: page >= totalPages ? "1px solid #f3f4f6" : "1px solid #e5e7eb",
                    fontSize: 14,
                    color: page >= totalPages ? "#d1d5db" : "#4b5563",
                    cursor: page >= totalPages ? "not-allowed" : "pointer",
                    backgroundColor: "#fff",
                    transition: "background-color 0.15s",
                  }}
                >
                  <ChevronRight style={{ width: 16, height: 16 }} />
                </button>
                <span style={{ marginLeft: 8, fontSize: 12, color: "#6b7280" }}>
                  Page {page} of {totalPages}
                </span>
              </div>
            )}
          </>
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
      <Button size="small" style={{ marginTop: 12 }} onClick={onRetry}>
        <RefreshCcw style={{ width: 14, height: 14 }} />
        Retry
      </Button>
    </div>
  );
}
