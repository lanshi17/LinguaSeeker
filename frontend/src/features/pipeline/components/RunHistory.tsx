import { useState, useCallback } from "react";
import { Activity, RefreshCcw, Search, X, ChevronLeft, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, Input } from "antd";
import { Skeleton } from "@/components/ui/Skeleton";
import { useI18n } from "@/lib/i18n";
import { usePagination } from "@/lib/hooks/usePagination";
import { RunListItem } from "./RunListItem";
import { usePipelineRuns } from "../hooks/usePipelineRuns";
import type { ProcessingStatus } from "../types/pipeline";

const PAGE_SIZE = 20;

/* ── Embedded styles for pagination ────────────────────────── */

const paginationCSS = `
.rh-page-btn:hover {
  background-color: var(--color-bg);
}
.rh-page-jump-input {
  width: 48px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  text-align: center;
  font-size: 13px;
  font-family: var(--font-mono);
  color: var(--color-text-strong);
  outline: none;
  transition: border-color 0.15s;
}
.rh-page-jump-input:focus {
  border-color: var(--color-primary-600);
  box-shadow: 0 0 0 2px var(--color-primary-100, rgba(8,145,178,0.15));
}
.rh-page-jump-input::placeholder {
  color: var(--color-text-muted);
}
`;

interface RunHistoryProps {
  className?: string;
  statusFilter?: ProcessingStatus | "all";
}

export function RunHistory({ className, statusFilter }: RunHistoryProps) {
  const { t } = useI18n();
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

  const { pageNumbers, canPrev, canNext, goPrev, goNext, goTo } = usePagination({
    page,
    totalPages,
    onPageChange: setPage,
  });

  const handleJump = useCallback(() => {
    const num = parseInt(jumpValue, 10);
    if (!Number.isNaN(num) && num >= 1 && num <= totalPages) {
      goTo(num);
      setJumpValue("");
    }
  }, [jumpValue, totalPages, goTo]);

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  return (
    <section
      className={className}
      style={{
        borderRadius: 12,
        border: "1px solid var(--color-border)",
        backgroundColor: "var(--color-surface)",
        boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
      }}
    >
      <style>{paginationCSS}</style>
      <header style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid var(--color-bg-muted)",
        padding: "14px 20px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Activity style={{ width: 16, height: 16, color: "var(--color-primary-600)" }} aria-hidden />
          <h2 style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em", color: "var(--color-text)", margin: 0 }}>
            {t("pipeline.history.title")}
          </h2>
          {!isLoading && (
            <span style={{
              borderRadius: 9999,
              backgroundColor: "var(--color-bg-muted)",
              padding: "2px 8px",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              fontVariantNumeric: "tabular-nums",
              color: "var(--color-text-strong)",
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
          aria-label={t("pipeline.history.refreshAria")}
        >
          <RefreshCcw style={{ width: 14, height: 14 }} />
          {t("pipeline.history.refresh")}
        </Button>
      </header>

      {/* Search bar */}
      <div style={{ padding: "12px 20px 0" }}>
        <Input
          placeholder={t("pipeline.history.searchPlaceholder")}
          prefix={<Search style={{ width: 14, height: 14, color: "var(--color-text-muted)" }} />}
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
                  color: "var(--color-text-muted)",
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
          <RunHistorySkeleton t={t} />
        ) : error ? (
          <RunHistoryError onRetry={() => refetch()} t={t} />
        ) : items.length === 0 ? (
          <RunHistoryEmpty hasFilter={Boolean(statusFilter && statusFilter !== "all") || !!search} t={t} />
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
                borderTop: "1px solid var(--color-bg-muted)",
              }}>
                <button
                  type="button"
                  onClick={goPrev}
                  disabled={!canPrev}
                  className={canPrev ? "rh-page-btn" : undefined}
                  style={{
                    display: "flex",
                    width: 36,
                    height: 36,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 8,
                    border: !canPrev ? "1px solid var(--color-bg-muted)" : "1px solid var(--color-border)",
                    fontSize: 14,
                    color: !canPrev ? "var(--color-text-muted)" : "var(--color-text-strong)",
                    cursor: !canPrev ? "not-allowed" : "pointer",
                    backgroundColor: "var(--color-surface)",
                    transition: "background-color 0.15s",
                  }}
                >
                  <ChevronLeft style={{ width: 16, height: 16 }} />
                </button>
                {pageNumbers.map((p, idx) => {
                  if (p < 0) {
                    return (
                      <span key={`ellipsis-${idx}`} style={{ padding: "0 4px", color: "var(--color-text-muted)", fontSize: 14 }}>
                        &hellip;
                      </span>
                    );
                  }
                  const isActive = p === page;
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => goTo(p)}
                      className={!isActive ? "rh-page-btn" : undefined}
                      style={{
                        display: "flex",
                        width: 36,
                        height: 36,
                        alignItems: "center",
                        justifyContent: "center",
                        borderRadius: 8,
                        border: isActive ? "1px solid var(--color-primary-600)" : "1px solid var(--color-border)",
                        fontSize: 14,
                        fontWeight: 500,
                        backgroundColor: isActive ? "var(--color-primary-600)" : "var(--color-surface)",
                        color: isActive ? "var(--color-surface)" : "var(--color-text-strong)",
                        cursor: "pointer",
                        transition: "background-color 0.15s",
                      }}
                    >
                      {p}
                    </button>
                  );
                })}
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
                  aria-label={t("pipeline.history.jumpToPage")}
                  title={t("pipeline.history.jumpToPageTitle", { total: String(totalPages) })}
                />
                <button
                  type="button"
                  onClick={goNext}
                  disabled={!canNext}
                  className={canNext ? "rh-page-btn" : undefined}
                  style={{
                    display: "flex",
                    width: 36,
                    height: 36,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 8,
                    border: !canNext ? "1px solid var(--color-bg-muted)" : "1px solid var(--color-border)",
                    fontSize: 14,
                    color: !canNext ? "var(--color-text-muted)" : "var(--color-text-strong)",
                    cursor: !canNext ? "not-allowed" : "pointer",
                    backgroundColor: "var(--color-surface)",
                    transition: "background-color 0.15s",
                  }}
                >
                  <ChevronRight style={{ width: 16, height: 16 }} />
                </button>
                <span style={{ marginLeft: 8, fontSize: 12, color: "var(--color-text-secondary)" }}>
                  {t("pipeline.history.pageInfo", { current: String(page), total: String(totalPages) })}
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

type TFn = (key: string, params?: Record<string, string>) => string;

function RunHistorySkeleton({ t }: { t: TFn }) {
  return (
    <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }} aria-label={t("pipeline.history.loadingAria")}>
      {Array.from({ length: 4 }).map((_, i) => (
        <li
          key={i}
          style={{
            borderRadius: 8,
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
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

function RunHistoryEmpty({ hasFilter, t }: { hasFilter: boolean; t: TFn }) {
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
          <p style={{ marginTop: 12, fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>
            {t("pipeline.history.noMatch")}
          </p>
          <p style={{ marginTop: 4, maxWidth: 384, fontSize: 12, color: "var(--color-text-secondary)" }}>
            {t("pipeline.history.filterEmpty", { status: "" })}
          </p>
        </>
      ) : (
        <>
          <p style={{ marginTop: 12, fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>{t("pipeline.history.noRuns")}</p>
          <p style={{ marginTop: 4, maxWidth: 384, fontSize: 12, color: "var(--color-text-secondary)" }}>
            {t("pipeline.history.guidance")}{" "}
            <Link to="/chat" style={{ fontWeight: 500, color: "var(--color-primary-600)" }}>
              {t("pipeline.history.chatLink")}
            </Link>
          </p>
        </>
      )}
    </div>
  );
}

function RunHistoryError({ onRetry, t }: { onRetry: () => void; t: TFn }) {
  return (
    <div style={{
      display: "grid",
      placeItems: "center",
      padding: "40px 24px",
      textAlign: "center",
    }}>
      <p style={{ fontSize: 14, color: "var(--color-error-text)", margin: 0 }}>{t("pipeline.history.loadError")}</p>
      <p style={{ marginTop: 4, maxWidth: 384, fontSize: 12, color: "var(--color-text-secondary)" }}>
        {t("pipeline.history.loadErrorHint")}
      </p>
      <Button size="small" style={{ marginTop: 12 }} onClick={onRetry}>
        <RefreshCcw style={{ width: 14, height: 14 }} />
        {t("pipeline.history.retry")}
      </Button>
    </div>
  );
}
