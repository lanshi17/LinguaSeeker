
import { AlertCircle, CheckCircle2, Circle, FileText, Hash, Layers, Loader2 } from "lucide-react";
import { Card } from "antd";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { LivePulse } from "@/components/ui/LivePulse";
import { MetricTile } from "@/components/ui/MetricTile";
import { useI18n } from "@/lib/i18n";
import { useElapsedSeconds } from "@/lib/hooks/useElapsedSeconds";
import { formatDuration, formatTimestamp } from "@/lib/utils/format";
import type { PhaseNode, PhaseStatus, ProcessingStatus } from "../types/pipeline";

interface PhaseDetailCardProps {
  phaseId: string;
  phase: PhaseStatus;
  index?: number;
}

const PHASE_ICON_COLOR: Record<string, React.CSSProperties> = {
  phase_1: { color: "var(--color-text-secondary)", borderBottom: "1px solid var(--color-border)" },
  phase_2: { color: "var(--color-text-secondary)", borderBottom: "1px solid var(--color-border)" },
  phase_3: { color: "var(--color-text-secondary)", borderBottom: "1px solid var(--color-border)" },
};

const DEFAULT_HEADER_STYLE: React.CSSProperties = { borderBottom: "1px solid var(--color-border)" };

const nodeBorderColorBg = (status: ProcessingStatus): React.CSSProperties => {
  switch (status) {
    case "running":
      return { borderColor: "var(--color-running-border)", backgroundColor: "var(--color-running-bg)" };
    case "completed":
      return { borderColor: "var(--color-success-200)", backgroundColor: "var(--color-highlight-green)" };
    case "failed":
      return { borderColor: "var(--color-error-border)", backgroundColor: "var(--color-error-bg)" };
    case "pending":
      return { borderColor: "var(--color-border)", backgroundColor: "var(--color-subtle-bg)" };
    case "skipped":
      return { borderColor: "var(--color-border)", backgroundColor: "var(--color-subtle-bg)" };
    default:
      return { borderColor: "var(--color-border)", backgroundColor: "var(--color-subtle-bg)" };
  }
};

const progressBarBg = (status: ProcessingStatus): string => {
  if (status === "running") return "var(--color-primary-600, #0891b2)";
  if (status === "completed") return "var(--color-success-500, #22c55e)";
  return "var(--color-text-muted)";
};

const PHASE_TITLE_KEYS: Record<string, string> = {
  phase_1: "pipeline.phase.acquisition",
  phase_2: "pipeline.phase.extraction",
  phase_3: "pipeline.phase.standardization",
};

const PHASE_DESC_KEYS: Record<string, string> = {
  phase_1: "pipeline.phase.acquisitionDesc",
  phase_2: "pipeline.phase.extractionDesc",
  phase_3: "pipeline.phase.standardizationDesc",
};

export function PhaseDetailCard({ phaseId, phase, index = 0 }: PhaseDetailCardProps) {
  const { t } = useI18n();
  const titleKey = PHASE_TITLE_KEYS[phaseId];
  const descKey = PHASE_DESC_KEYS[phaseId];
  const title = titleKey ? t(titleKey) : phaseId;
  const subtitle = descKey ? t(descKey) : "";
  const isLive = phase.status === "running";
  const elapsed = useElapsedSeconds(isLive ? phase.started_at : phase.completed_at);
  const duration = phase.duration_seconds ?? (isLive ? elapsed : elapsed);
  const nodes = phase.nodes ?? [];
  const totalNodes = nodes.length;
  const doneNodes = nodes.filter((n) => n.status === "completed").length;
  const totalCount = nodes.reduce((acc, n) => acc + (n.count ?? 0), 0) + (phase.count ?? 0);

  return (
    <Card
      styles={{ body: { padding: 0 } }}
      className="stagger-in"
      style={{ display: "flex", flexDirection: "column", overflow: "hidden", animationDelay: `${index * 70}ms` }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
          borderBottom: "1px solid var(--color-bg-muted)",
          padding: "12px 16px",
          ...(PHASE_ICON_COLOR[phaseId] ?? DEFAULT_HEADER_STYLE),
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Layers style={{ width: 14, height: 14 }} aria-hidden />
            <h3
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--color-text-secondary)",
              }}
            >
              {title}
            </h3>
          </div>
          {subtitle && (
            <p
              style={{
                marginTop: 2,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                fontSize: 11,
                color: "var(--color-text-strong)",
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
        <PhaseStatusBadge status={phase.status} t={t} />
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, padding: "12px 16px" }}>
        <MetricTile
          label={t("pipeline.phase.duration")}
          value={formatDuration(duration)}
          icon={<FileText style={{ width: 12, height: 12 }} aria-hidden />}
        />
        <MetricTile
          label={t("pipeline.phase.nodes")}
          value={totalNodes > 0 ? `${doneNodes}/${totalNodes}` : "—"}
          tone={totalNodes > 0 && doneNodes === totalNodes ? "success" : "default"}
          icon={<Hash style={{ width: 12, height: 12 }} aria-hidden />}
        />
        <MetricTile
          label={t("pipeline.phase.items")}
          value={totalCount > 0 ? totalCount.toLocaleString() : "—"}
          tone="primary"
          icon={<Layers style={{ width: 12, height: 12 }} aria-hidden />}
        />
      </div>

      <div style={{ borderTop: "1px solid var(--color-bg-muted)", padding: "12px 16px" }}>
        {totalNodes > 0 ? (
          <NodeList nodes={nodes} t={t} />
        ) : phase.summary ? (
          <SummaryBlock summary={phase.summary} />
        ) : isLive ? (
          <EmptyLiveHint phaseId={phaseId} t={t} />
        ) : (
          <p style={{ fontSize: 11, fontStyle: "italic", color: "var(--color-text-muted)" }}>
            {t("pipeline.phase.noDetail")}
          </p>
        )}
      </div>

      <footer
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid var(--color-bg-muted)",
          backgroundColor: "var(--color-subtle-bg)",
          padding: "8px 16px",
          fontSize: 10,
          fontFamily: "var(--font-mono, monospace)",
          fontVariantNumeric: "tabular-nums",
          color: "var(--color-text-secondary)",
        }}
      >
        <span>{t("pipeline.phase.started")} {formatTimestamp(phase.started_at)}</span>
        {phase.completed_at && <span>{t("pipeline.phase.done")} {formatTimestamp(phase.completed_at)}</span>}
      </footer>

      {phase.error && (
        <div
          style={{
            borderTop: "1px solid var(--color-error-border)",
            backgroundColor: "var(--color-error-bg)",
            padding: "8px 16px",
            fontSize: 11,
            color: "var(--color-error-text)",
          }}
        >
          <AlertCircle style={{ marginRight: 4, display: "inline", width: 12, height: 12 }} aria-hidden />
          {stringifyError(phase.error, t("pipeline.phase.unknownError"))}
        </div>
      )}
    </Card>
  );
}

type TFn = (key: string, params?: Record<string, string>) => string;

function PhaseStatusBadge({ status, t }: { status: ProcessingStatus; t: TFn }) {
  if (status === "running") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          borderRadius: 9999,
          backgroundColor: "var(--color-card-bg)",
          padding: "2px 8px",
          fontSize: 11,
          fontWeight: 500,
          color: "var(--color-primary-700, var(--color-primary-700))",
          border: "1px solid var(--color-running-border)",
        }}
      >
        <LivePulse tone="primary" />
        {t("pipeline.phase.running")}
      </span>
    );
  }
  if (status === "completed") {
    return <Badge variant="success">{t("pipeline.phase.completed")}</Badge>;
  }
  if (status === "failed") {
    return <Badge variant="error">{t("pipeline.phase.failed")}</Badge>;
  }
  if (status === "skipped") {
    return <Badge variant="default">{t("pipeline.phase.skipped")}</Badge>;
  }
  return <Badge variant="default">{t("pipeline.phase.pending")}</Badge>;
}

function NodeList({ nodes, t }: { nodes: PhaseNode[]; t: TFn }) {
  return (
    <ul style={{ display: "flex", flexDirection: "column", gap: 6 }} aria-label={t("pipeline.phase.subnodes")}>
      {nodes.map((node) => (
        <NodeRow key={node.node_id} node={node} />
      ))}
    </ul>
  );
}

function NodeRow({ node }: { node: PhaseNode }) {
  const elapsed = useElapsedSeconds(
    node.status === "running" ? node.started_at : node.completed_at,
  );
  const duration = node.duration_seconds ?? elapsed;
  const progressPct =
    node.progress != null
      ? Math.min(100, Math.max(0, node.progress * 100))
      : node.status === "completed"
        ? 100
        : 0;

  return (
    <li
      style={{
        borderRadius: 6,
        border: "1px solid",
        padding: "6px 10px",
        transition: "color 150ms, background-color 150ms",
        ...nodeBorderColorBg(node.status),
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <NodeStatusIcon status={node.status} />
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            fontSize: 12,
            fontWeight: 500,
            color: "var(--color-code-text)",
          }}
        >
          {node.label}
        </span>
        {node.count != null && node.count > 0 && (
          <span
            style={{
              marginLeft: "auto",
              borderRadius: 4,
              backgroundColor: "var(--color-card-bg)",
              padding: "2px 6px",
              fontFamily: "var(--font-mono, monospace)",
              fontSize: 10,
              fontVariantNumeric: "tabular-nums",
              color: "var(--color-text-strong)",
            }}
          >
            {node.count.toLocaleString()}
          </span>
        )}
        <span
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 10,
            fontVariantNumeric: "tabular-nums",
            color: "var(--color-text-secondary)",
          }}
        >
          {formatDuration(duration)}
        </span>
      </div>
      {(node.status === "running" || node.progress != null) && (
        <div
          style={{
            marginTop: 4,
            height: 2,
            overflow: "hidden",
            borderRadius: 9999,
            backgroundColor: "var(--color-card-bg)",
          }}
        >
          <div
            className={node.status === "running" ? "progress-stripe" : undefined}
            style={{
              height: "100%",
              borderRadius: 9999,
              transition: "width 500ms",
              backgroundColor: progressBarBg(node.status),
              width: `${progressPct}%`,
            }}
          />
        </div>
      )}
    </li>
  );
}

function NodeStatusIcon({ status }: { status: ProcessingStatus }) {
  if (status === "running")
    return <Loader2 className="spin" style={{ width: 14, height: 14, flexShrink: 0, color: "var(--color-primary-600, var(--color-primary-600))" }} aria-hidden />;
  if (status === "completed")
    return <CheckCircle2 style={{ width: 14, height: 14, flexShrink: 0, color: "var(--color-success-600)" }} aria-hidden />;
  if (status === "failed")
    return <AlertCircle style={{ width: 14, height: 14, flexShrink: 0, color: "var(--color-error-text)" }} aria-hidden />;
  return <Circle style={{ width: 14, height: 14, flexShrink: 0, color: "var(--color-text-muted)" }} aria-hidden />;
}

function SummaryBlock({ summary }: { summary: Record<string, unknown> }) {
  const entries = Object.entries(summary).slice(0, 4);
  if (entries.length === 0) return null;
  return (
    <dl
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        gap: "4px 12px",
        fontSize: 11,
      }}
    >
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, overflow: "hidden" }}>
          <dt style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--color-text-secondary)" }}>
            {k.replace(/_/g, " ")}
          </dt>
          <dd
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontFamily: "var(--font-mono, monospace)",
              fontVariantNumeric: "tabular-nums",
              color: "var(--color-code-text)",
            }}
          >
            {typeof v === "number" ? v.toLocaleString() : String(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function EmptyLiveHint({ phaseId, t }: { phaseId: string; t: TFn }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--color-text-secondary)" }}>
      <Skeleton variant="line" width={128} height={8} />
      <Skeleton variant="line" width={80} height={8} />
      <span style={{ marginLeft: "auto", fontStyle: "italic", color: "var(--color-text-muted)" }}>
        {t("pipeline.phase.preparing", { phase: phaseId.replace("_", " ") })}
      </span>
    </div>
  );
}

function stringifyError(err: unknown, fallback: string): string {
  if (typeof err === "string") return err;
  if (err && typeof err === "object") {
    const m = (err as { message?: unknown }).message;
    if (typeof m === "string") return m;
    try {
      return JSON.stringify(err);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

export function PhaseDetailCardSkeleton({ index = 0 }: { index?: number }) {
  return (
    <Card
      styles={{ body: { padding: 0 } }}
      className="stagger-in"
      style={{ display: "flex", flexDirection: "column", overflow: "hidden", animationDelay: `${index * 70}ms` }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          borderBottom: "1px solid var(--color-bg-muted)",
          padding: "12px 16px",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <Skeleton width={144} height={12} />
          <Skeleton width={192} height={8} />
        </div>
        <Skeleton variant="pill" width={64} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, padding: "12px 16px" }}>
        <Skeleton variant="block" height={48} />
        <Skeleton variant="block" height={48} />
        <Skeleton variant="block" height={48} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, borderTop: "1px solid var(--color-bg-muted)", padding: "12px 16px" }}>
        <Skeleton width="100%" height={12} />
        <Skeleton width="83%" height={12} />
        <Skeleton width="67%" height={12} />
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid var(--color-bg-muted)",
          backgroundColor: "var(--color-subtle-bg)",
          padding: "8px 16px",
        }}
      >
        <Skeleton width={128} height={8} />
        <Skeleton width={80} height={8} />
      </div>
    </Card>
  );
}
