
import { AlertCircle, CheckCircle2, Circle, FileText, Hash, Layers, Loader2 } from "lucide-react";
import { Card } from "antd";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { LivePulse } from "@/components/ui/LivePulse";
import { MetricTile } from "@/components/ui/MetricTile";
import { useElapsedSeconds } from "@/lib/hooks/useElapsedSeconds";
import { formatDuration, formatTimestamp } from "@/lib/utils/format";
import type { PhaseNode, PhaseStatus, ProcessingStatus } from "../types/pipeline";

interface PhaseDetailCardProps {
  phaseId: string;
  phase: PhaseStatus;
  index?: number;
}

const PHASE_LABELS: Record<string, { title: string; subtitle: string }> = {
  phase_1: {
    title: "Document Acquisition",
    subtitle: "Literature search, download, OCR & parse",
  },
  phase_2: {
    title: "Evidence Extraction",
    subtitle: "Cross-lingual extraction & fusion",
  },
  phase_3: {
    title: "Entity Standardization",
    subtitle: "Terminology alignment & knowledge graph",
  },
};

const PHASE_ICON_COLOR: Record<string, React.CSSProperties> = {
  phase_1: { color: "#0369a1", backgroundColor: "#f0f9ff", borderBottom: "1px solid #bae6fd" },
  phase_2: { color: "var(--color-primary-700, #0e7490)", backgroundColor: "#ecfeff", borderBottom: "1px solid #a5f3fc" },
  phase_3: { color: "#6d28d9", backgroundColor: "#f5f3ff", borderBottom: "1px solid #ddd6fe" },
};

const DEFAULT_HEADER_STYLE: React.CSSProperties = { backgroundColor: "#f9fafb" };

const nodeBorderColorBg = (status: ProcessingStatus): React.CSSProperties => {
  switch (status) {
    case "running":
      return { borderColor: "#a5f3fc", backgroundColor: "rgba(236,254,255,0.4)" };
    case "completed":
      return { borderColor: "#bbf7d0", backgroundColor: "rgba(240,253,244,0.3)" };
    case "failed":
      return { borderColor: "#fecaca", backgroundColor: "rgba(254,242,242,0.4)" };
    case "pending":
      return { borderColor: "#e5e7eb", backgroundColor: "rgba(249,250,251,0.5)" };
    case "skipped":
      return { borderColor: "#e5e7eb", backgroundColor: "rgba(249,250,251,0.3)" };
    default:
      return { borderColor: "#e5e7eb", backgroundColor: "rgba(249,250,251,0.5)" };
  }
};

const progressBarBg = (status: ProcessingStatus): string => {
  if (status === "running") return "linear-gradient(to right, #7dd3fc, var(--color-primary-600, #0891b2))";
  if (status === "completed") return "var(--color-success-500, #22c55e)";
  return "#d1d5db";
};

export function PhaseDetailCard({ phaseId, phase, index = 0 }: PhaseDetailCardProps) {
  const meta = PHASE_LABELS[phaseId] ?? { title: phaseId, subtitle: "" };
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
          borderBottom: "1px solid #f3f4f6",
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
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: "-0.025em",
                color: "#111827",
              }}
            >
              {meta.title}
            </h3>
          </div>
          {meta.subtitle && (
            <p
              style={{
                marginTop: 2,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                fontSize: 11,
                color: "#4b5563",
              }}
            >
              {meta.subtitle}
            </p>
          )}
        </div>
        <PhaseStatusBadge status={phase.status} />
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, padding: "12px 16px" }}>
        <MetricTile
          label="Duration"
          value={formatDuration(duration)}
          icon={<FileText style={{ width: 12, height: 12 }} aria-hidden />}
        />
        <MetricTile
          label="Nodes"
          value={totalNodes > 0 ? `${doneNodes}/${totalNodes}` : "—"}
          tone={totalNodes > 0 && doneNodes === totalNodes ? "success" : "default"}
          icon={<Hash style={{ width: 12, height: 12 }} aria-hidden />}
        />
        <MetricTile
          label="Items"
          value={totalCount > 0 ? totalCount.toLocaleString() : "—"}
          tone="primary"
          icon={<Layers style={{ width: 12, height: 12 }} aria-hidden />}
        />
      </div>

      <div style={{ borderTop: "1px solid #f3f4f6", padding: "12px 16px" }}>
        {totalNodes > 0 ? (
          <NodeList nodes={nodes} />
        ) : phase.summary ? (
          <SummaryBlock summary={phase.summary} />
        ) : isLive ? (
          <EmptyLiveHint phaseId={phaseId} />
        ) : (
          <p style={{ fontSize: 11, fontStyle: "italic", color: "#9ca3af" }}>
            No sub-node detail available.
          </p>
        )}
      </div>

      <footer
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid #f3f4f6",
          backgroundColor: "rgba(249,250,251,0.5)",
          padding: "8px 16px",
          fontSize: 10,
          fontFamily: "var(--font-mono, monospace)",
          fontVariantNumeric: "tabular-nums",
          color: "#6b7280",
        }}
      >
        <span>Started {formatTimestamp(phase.started_at)}</span>
        {phase.completed_at && <span>Done {formatTimestamp(phase.completed_at)}</span>}
      </footer>

      {phase.error && (
        <div
          style={{
            borderTop: "1px solid #fecaca",
            backgroundColor: "#fef2f2",
            padding: "8px 16px",
            fontSize: 11,
            color: "#b91c1c",
          }}
        >
          <AlertCircle style={{ marginRight: 4, display: "inline", width: 12, height: 12 }} aria-hidden />
          {stringifyError(phase.error)}
        </div>
      )}
    </Card>
  );
}

function PhaseStatusBadge({ status }: { status: ProcessingStatus }) {
  if (status === "running") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          borderRadius: 9999,
          backgroundColor: "rgba(255,255,255,0.7)",
          padding: "2px 8px",
          fontSize: 11,
          fontWeight: 500,
          color: "var(--color-primary-700, #0e7490)",
          border: "1px solid #a5f3fc",
        }}
      >
        <LivePulse tone="primary" />
        Running
      </span>
    );
  }
  if (status === "completed") {
    return <Badge variant="success">Completed</Badge>;
  }
  if (status === "failed") {
    return <Badge variant="error">Failed</Badge>;
  }
  if (status === "skipped") {
    return <Badge variant="default">Skipped</Badge>;
  }
  return <Badge variant="default">Pending</Badge>;
}

function NodeList({ nodes }: { nodes: PhaseNode[] }) {
  return (
    <ul style={{ display: "flex", flexDirection: "column", gap: 6 }} aria-label="Sub-nodes">
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
            color: "#1f2937",
          }}
        >
          {node.label}
        </span>
        {node.count != null && node.count > 0 && (
          <span
            style={{
              marginLeft: "auto",
              borderRadius: 4,
              backgroundColor: "rgba(255,255,255,0.7)",
              padding: "2px 6px",
              fontFamily: "var(--font-mono, monospace)",
              fontSize: 10,
              fontVariantNumeric: "tabular-nums",
              color: "#374151",
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
            color: "#6b7280",
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
            backgroundColor: "rgba(255,255,255,0.6)",
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
    return <Loader2 className="spin" style={{ width: 14, height: 14, flexShrink: 0, color: "var(--color-primary-600, #0891b2)" }} aria-hidden />;
  if (status === "completed")
    return <CheckCircle2 style={{ width: 14, height: 14, flexShrink: 0, color: "#16a34a" }} aria-hidden />;
  if (status === "failed")
    return <AlertCircle style={{ width: 14, height: 14, flexShrink: 0, color: "#dc2626" }} aria-hidden />;
  return <Circle style={{ width: 14, height: 14, flexShrink: 0, color: "#9ca3af" }} aria-hidden />;
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
          <dt style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#6b7280" }}>
            {k.replace(/_/g, " ")}
          </dt>
          <dd
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontFamily: "var(--font-mono, monospace)",
              fontVariantNumeric: "tabular-nums",
              color: "#1f2937",
            }}
          >
            {typeof v === "number" ? v.toLocaleString() : String(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function EmptyLiveHint({ phaseId }: { phaseId: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "#6b7280" }}>
      <Skeleton variant="line" width={128} height={8} />
      <Skeleton variant="line" width={80} height={8} />
      <span style={{ marginLeft: "auto", fontStyle: "italic", color: "#9ca3af" }}>
        preparing {phaseId.replace("_", " ")}…
      </span>
    </div>
  );
}

function stringifyError(err: unknown): string {
  if (typeof err === "string") return err;
  if (err && typeof err === "object") {
    const m = (err as { message?: unknown }).message;
    if (typeof m === "string") return m;
    try {
      return JSON.stringify(err);
    } catch {
      return "Unknown error";
    }
  }
  return "Unknown error";
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
          borderBottom: "1px solid #f3f4f6",
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
      <div style={{ display: "flex", flexDirection: "column", gap: 6, borderTop: "1px solid #f3f4f6", padding: "12px 16px" }}>
        <Skeleton width="100%" height={12} />
        <Skeleton width="83%" height={12} />
        <Skeleton width="67%" height={12} />
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid #f3f4f6",
          backgroundColor: "rgba(249,250,251,0.5)",
          padding: "8px 16px",
        }}
      >
        <Skeleton width={128} height={8} />
        <Skeleton width={80} height={8} />
      </div>
    </Card>
  );
}
