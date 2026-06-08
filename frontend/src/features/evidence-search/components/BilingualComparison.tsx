"use client";

import type {
  EvidenceGroupDetailResponse,
  EvidenceTrackTrace,
} from "../types/evidenceSearch";
import { EvidenceHighlightText } from "./EvidenceHighlightText";

interface BilingualComparisonTraceProps {
  trace: EvidenceTrackTrace | null;
}

interface BilingualComparisonDetailProps {
  detail: EvidenceGroupDetailResponse;
  groupId: string;
  selectedEvidenceId: string | null;
  setSelectedEvidenceId: (next: string | null) => void;
}

export type BilingualComparisonProps =
  | BilingualComparisonTraceProps
  | BilingualComparisonDetailProps;

function isDetailProps(
  props: BilingualComparisonProps,
): props is BilingualComparisonDetailProps {
  return (props as BilingualComparisonDetailProps).detail !== undefined;
}

function selectTrace(
  detail: EvidenceGroupDetailResponse,
  selectedEvidenceId: string | null,
): EvidenceTrackTrace | null {
  if (!selectedEvidenceId) {
    return detail.traces[0] ?? null;
  }
  const selectedItem = detail.items.find(
    (item) => item.canonical_evidence_id === selectedEvidenceId,
  );
  return (
    detail.traces.find(
      (trace) => trace.canonical_evidence_id === selectedEvidenceId,
    ) ??
    detail.traces.find((trace) => trace.field_id === selectedItem?.field_id) ??
    detail.traces[0] ??
    null
  );
}

export function BilingualComparison(props: BilingualComparisonProps) {
  if (!isDetailProps(props)) {
    return <TraceComparisonPanel trace={props.trace} />;
  }

  const { detail, groupId, selectedEvidenceId, setSelectedEvidenceId } = props;
  const trace = selectTrace(detail, selectedEvidenceId);

  if (detail.traces.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-gray-400">
        No bilingual traces for this evidence group.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <EvidenceSelector
        detail={detail}
        groupId={groupId}
        selectedEvidenceId={selectedEvidenceId}
        setSelectedEvidenceId={setSelectedEvidenceId}
      />
      <TraceComparisonPanel trace={trace} />
    </div>
  );
}

function TraceComparisonPanel({ trace }: { trace: EvidenceTrackTrace | null }) {
  if (!trace) {
    return (
      <p className="py-8 text-center text-sm text-gray-400">No evidence selected.</p>
    );
  }

  return (
    <>
      <div className="mb-4 grid gap-3 rounded-md bg-slate-50 p-3 xl:grid-cols-2">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Original value
          </p>
          <p className="mt-1 break-words font-mono text-sm text-slate-900">
            {trace.original_value ?? "—"}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Translated value
          </p>
          <p className="mt-1 break-words font-mono text-sm text-slate-900">
            {trace.translated_value ?? "—"}
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <section>
          <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">
            Original
          </h4>
          <EvidenceHighlightText
            active
            anchorValue={trace.original_value ?? undefined}
            highlight={trace.original}
          />
        </section>
        <section>
          <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">
            Translated
          </h4>
          <EvidenceHighlightText
            active
            anchorValue={trace.translated_value ?? undefined}
            highlight={trace.translated}
          />
        </section>
      </div>
    </>
  );
}

function EvidenceSelector({
  detail,
  groupId,
  selectedEvidenceId,
  setSelectedEvidenceId,
}: {
  detail: EvidenceGroupDetailResponse;
  groupId: string;
  selectedEvidenceId: string | null;
  setSelectedEvidenceId: (next: string | null) => void;
}) {
  const activeId = selectedEvidenceId ?? detail.items[0]?.canonical_evidence_id ?? null;
  return (
    <div className="rounded-md border border-gray-200 bg-white p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
        Evidence item
      </p>
      <select
        aria-label="Select evidence item"
        className="mt-2 w-full rounded-md border border-gray-200 bg-white p-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none"
        value={activeId ?? ""}
        onChange={(event) => {
          const next = event.target.value || null;
          setSelectedEvidenceId(next);
          if (typeof window !== "undefined" && next) {
            const url = new URL(window.location.href);
            url.searchParams.set("groupId", groupId);
            url.searchParams.set("evidenceId", next);
            window.history.replaceState(null, "", url.toString());
          }
        }}
      >
        {detail.items.map((item) => (
          <option
            key={item.canonical_evidence_id}
            value={item.canonical_evidence_id}
          >
            {item.field_name ?? item.field_id} — {item.value ?? "(no value)"}
          </option>
        ))}
      </select>
    </div>
  );
}
