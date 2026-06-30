import type {
  EvidenceGroupDetailResponse,
  EvidenceTrackTrace,
} from "../types/evidenceSearch";
import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
  if (!isDetailProps(props)) {
    return <TraceComparisonPanel trace={props.trace} />;
  }

  const { detail, groupId, selectedEvidenceId, setSelectedEvidenceId } = props;
  const trace = selectTrace(detail, selectedEvidenceId);

  if (detail.traces.length === 0) {
    return (
      <p style={{ padding: "32px 0", textAlign: "center", fontSize: 14, color: "#9ca3af" }}>
        {t("evidence.compare.noTraces")}
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
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

export function TraceComparisonPanel({ trace }: { trace: EvidenceTrackTrace | null }) {
  const { t } = useI18n();
  if (!trace) {
    return (
      <p style={{ padding: "32px 0", textAlign: "center", fontSize: 14, color: "#9ca3af" }}>
        {t("evidence.compare.noSelected")}
      </p>
    );
  }

  return (
    <>
      <div
        className="bc-value-grid"
        style={{
          marginBottom: 16,
          borderRadius: 6,
          backgroundColor: "#f8fafc",
          padding: 12,
        }}
      >
        <div>
          <p style={{ fontSize: 10, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", color: "#64748b", margin: 0 }}>
            {t("evidence.compare.original")}
          </p>
          <p style={{ marginTop: 4, wordBreak: "break-word", fontFamily: "var(--font-mono)", fontSize: 14, color: "#0f172a", margin: "4px 0 0" }}>
            {trace.original_value ?? "—"}
          </p>
        </div>
        <div>
          <p style={{ fontSize: 10, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", color: "#64748b", margin: 0 }}>
            {t("evidence.compare.translated")}
          </p>
          <p style={{ marginTop: 4, wordBreak: "break-word", fontFamily: "var(--font-mono)", fontSize: 14, color: "#0f172a", margin: "4px 0 0" }}>
            {trace.translated_value ?? "—"}
          </p>
        </div>
      </div>

      <div className="bc-compare-grid">
        <section>
          <h4 style={{ marginBottom: 8, fontSize: 12, fontWeight: 500, textTransform: "uppercase", color: "#9ca3af", margin: "0 0 8px" }}>
            {t("evidence.compare.originalLabel")}
          </h4>
          <EvidenceHighlightText
            active
            anchorValue={trace.original_value ?? undefined}
            highlight={trace.original}
          />
        </section>
        <section>
          <h4 style={{ marginBottom: 8, fontSize: 12, fontWeight: 500, textTransform: "uppercase", color: "#9ca3af", margin: "0 0 8px" }}>
            {t("evidence.compare.translatedLabel")}
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
  const { t } = useI18n();
  const activeId = selectedEvidenceId ?? detail.items[0]?.canonical_evidence_id ?? null;
  return (
    <div style={{ borderRadius: 6, border: "1px solid #e5e7eb", backgroundColor: "#fff", padding: 12 }}>
      <p style={{ fontSize: 10, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", color: "#64748b", margin: 0 }}>
        {t("evidence.compare.itemLabel")}
      </p>
      <select
        aria-label={t("evidence.bilingual.selectItem")}
        style={{
          marginTop: 8,
          width: "100%",
          borderRadius: 6,
          border: "1px solid #e5e7eb",
          backgroundColor: "#fff",
          padding: 8,
          fontSize: 14,
          color: "#111827",
          outline: "none",
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = "var(--color-primary-500)";
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = "#e5e7eb";
        }}
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
            {item.field_name ?? item.field_id} — {item.value ?? t("evidence.compare.noValue")}
          </option>
        ))}
      </select>
    </div>
  );
}
