
import { AlertCircle, CheckCircle2, Circle, FileText, Hash, Layers, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { LivePulse } from "@/components/ui/LivePulse";
import { MetricTile } from "@/components/ui/MetricTile";
import { useElapsedSeconds } from "@/lib/hooks/useElapsedSeconds";
import { formatDuration, formatTimestamp } from "@/lib/utils/format";
import type { PhaseNode, PhaseStatus, ProcessingStatus } from "../types/pipeline";
import { cn } from "@/lib/utils/cn";

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

const PHASE_ICON_COLOR: Record<string, string> = {
  phase_1: "text-sky-700 bg-sky-50 border-sky-200",
  phase_2: "text-primary-700 bg-primary-50 border-primary-200",
  phase_3: "text-violet-700 bg-violet-50 border-violet-200",
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
      noPadding
      className="stagger-in flex flex-col overflow-hidden"
      style={{ animationDelay: `${index * 70}ms` }}
    >
      <header
        className={cn(
          "flex items-start justify-between gap-3 border-b border-gray-100 px-4 py-3",
          PHASE_ICON_COLOR[phaseId] ?? "bg-gray-50",
        )}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Layers className="h-3.5 w-3.5" aria-hidden />
            <h3 className="truncate text-[13px] font-semibold tracking-tight text-gray-900">
              {meta.title}
            </h3>
          </div>
          {meta.subtitle && (
            <p className="mt-0.5 truncate text-[11px] text-gray-600">{meta.subtitle}</p>
          )}
        </div>
        <PhaseStatusBadge status={phase.status} />
      </header>

      <div className="grid grid-cols-3 gap-2 px-4 py-3">
        <MetricTile
          label="Duration"
          value={formatDuration(duration)}
          icon={<FileText className="h-3 w-3" aria-hidden />}
        />
        <MetricTile
          label="Nodes"
          value={totalNodes > 0 ? `${doneNodes}/${totalNodes}` : "—"}
          tone={totalNodes > 0 && doneNodes === totalNodes ? "success" : "default"}
          icon={<Hash className="h-3 w-3" aria-hidden />}
        />
        <MetricTile
          label="Items"
          value={totalCount > 0 ? totalCount.toLocaleString() : "—"}
          tone="primary"
          icon={<Layers className="h-3 w-3" aria-hidden />}
        />
      </div>

      <div className="border-t border-gray-100 px-4 py-3">
        {totalNodes > 0 ? (
          <NodeList nodes={nodes} />
        ) : phase.summary ? (
          <SummaryBlock summary={phase.summary} />
        ) : isLive ? (
          <EmptyLiveHint phaseId={phaseId} />
        ) : (
          <p className="text-[11px] italic text-gray-400">
            No sub-node detail available.
          </p>
        )}
      </div>

      <footer className="flex items-center justify-between border-t border-gray-100 bg-gray-50/50 px-4 py-2 text-[10px] font-mono tabular-nums text-gray-500">
        <span>Started {formatTimestamp(phase.started_at)}</span>
        {phase.completed_at && <span>Done {formatTimestamp(phase.completed_at)}</span>}
      </footer>

      {phase.error && (
        <div className="border-t border-red-200 bg-red-50 px-4 py-2 text-[11px] text-red-700">
          <AlertCircle className="mr-1 inline h-3 w-3" aria-hidden />
          {stringifyError(phase.error)}
        </div>
      )}
    </Card>
  );
}

function PhaseStatusBadge({ status }: { status: ProcessingStatus }) {
  if (status === "running") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-medium text-primary-700 ring-1 ring-primary-200">
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
  if (status === "awaiting_review") {
    return <Badge variant="warning">Awaiting Review</Badge>;
  }
  return <Badge variant="default">Pending</Badge>;
}

function NodeList({ nodes }: { nodes: PhaseNode[] }) {
  return (
    <ul className="space-y-1.5" aria-label="Sub-nodes">
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
      className={cn(
        "group rounded-md border px-2.5 py-1.5 transition-colors",
        node.status === "running" && "border-primary-200 bg-primary-50/40",
        node.status === "completed" && "border-success-200 bg-success-50/30",
        node.status === "failed" && "border-red-200 bg-red-50/40",
        node.status === "pending" && "border-gray-200 bg-gray-50/50",
        node.status === "skipped" && "border-gray-200 bg-gray-50/30",
      )}
    >
      <div className="flex items-center gap-2">
        <NodeStatusIcon status={node.status} />
        <span className="truncate text-[12px] font-medium text-gray-800">
          {node.label}
        </span>
        {node.count != null && node.count > 0 && (
          <span className="ml-auto rounded bg-white/70 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-gray-700">
            {node.count.toLocaleString()}
          </span>
        )}
        <span className="font-mono text-[10px] tabular-nums text-gray-500">
          {formatDuration(duration)}
        </span>
      </div>
      {(node.status === "running" || node.progress != null) && (
        <div className="mt-1 h-0.5 overflow-hidden rounded-full bg-white/60">
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-500",
              node.status === "running"
                ? "bg-gradient-to-r from-primary-300 to-primary-600 progress-stripe"
                : node.status === "completed"
                  ? "bg-success-500"
                  : "bg-gray-300",
            )}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      )}
    </li>
  );
}

function NodeStatusIcon({ status }: { status: ProcessingStatus }) {
  if (status === "running")
    return <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary-600" aria-hidden />;
  if (status === "completed")
    return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-success-600" aria-hidden />;
  if (status === "failed")
    return <AlertCircle className="h-3.5 w-3.5 shrink-0 text-red-600" aria-hidden />;
  return <Circle className="h-3.5 w-3.5 shrink-0 text-gray-400" aria-hidden />;
}

function SummaryBlock({ summary }: { summary: Record<string, unknown> }) {
  const entries = Object.entries(summary).slice(0, 4);
  if (entries.length === 0) return null;
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-2 truncate">
          <dt className="truncate text-gray-500">{k.replace(/_/g, " ")}</dt>
          <dd className="truncate font-mono tabular-nums text-gray-800">
            {typeof v === "number" ? v.toLocaleString() : String(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function EmptyLiveHint({ phaseId }: { phaseId: string }) {
  return (
    <div className="flex items-center gap-2 text-[11px] text-gray-500">
      <Skeleton variant="line" width="w-32" className="h-2" />
      <Skeleton variant="line" width="w-20" className="h-2" />
      <span className="ml-auto italic text-gray-400">preparing {phaseId.replace("_", " ")}…</span>
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
      noPadding
      className="stagger-in flex flex-col overflow-hidden"
      style={{ animationDelay: `${index * 70}ms` }}
    >
      <div className="flex items-start justify-between border-b border-gray-100 px-4 py-3">
        <div className="space-y-1.5">
          <Skeleton width="w-36" height="h-3" />
          <Skeleton width="w-48" height="h-2" />
        </div>
        <Skeleton variant="pill" width="w-16" />
      </div>
      <div className="grid grid-cols-3 gap-2 px-4 py-3">
        <Skeleton variant="block" className="h-12" />
        <Skeleton variant="block" className="h-12" />
        <Skeleton variant="block" className="h-12" />
      </div>
      <div className="space-y-1.5 border-t border-gray-100 px-4 py-3">
        <Skeleton width="w-full" height="h-3" />
        <Skeleton width="w-5/6" height="h-3" />
        <Skeleton width="w-4/6" height="h-3" />
      </div>
      <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50/50 px-4 py-2">
        <Skeleton width="w-32" height="h-2" />
        <Skeleton width="w-20" height="h-2" />
      </div>
    </Card>
  );
}
