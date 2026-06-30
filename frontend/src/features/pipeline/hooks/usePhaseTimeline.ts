
import { useMemo } from "react";
import type { PipelineStatusResponse, PhaseTimelineStep } from "../types/pipeline";

function getPhaseLabels(t: (key: string) => string): Record<string, string> {
  return {
    phase_1: t("pipeline.phase.acquisition"),
    phase_2: t("pipeline.phase.extraction"),
    phase_3: t("pipeline.phase.standardization"),
  };
}

/**
 * Project a PipelineStatusResponse into PhaseTimelineStep[]
 * for consumption by the PhaseTimeline presentational component.
 *
 * Backend returns phases as a dict keyed by phase_id.
 * We convert to an ordered array for the timeline UI.
 */
export function usePhaseTimeline(
  status: PipelineStatusResponse | undefined,
  t: (key: string) => string,
): PhaseTimelineStep[] {
  const PHASE_LABELS = useMemo(() => getPhaseLabels(t), [t]);
  return useMemo(() => {
    if (!status?.phases) return [];

    const phaseOrder: Array<"phase_1" | "phase_2" | "phase_3"> = [
      "phase_1",
      "phase_2",
      "phase_3",
    ];

    return phaseOrder
      .filter((id) => status.phases[id])
      .map((id) => {
        const phase = status.phases[id];
        return {
          phaseId: id,
          label: PHASE_LABELS[id] ?? id,
          status: phase.status,
          duration: phase.duration_seconds,
        };
      });
  }, [status, PHASE_LABELS]);
}
