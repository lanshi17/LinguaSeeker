"use client";

import { useMemo } from "react";
import type { PipelineStatusResponse, PhaseTimelineStep } from "../types/pipeline";

const PHASE_LABELS: Record<string, string> = {
  phase_1: "Document Acquisition",
  phase_2: "Evidence Extraction",
  phase_3: "Entity Standardization",
};

/**
 * Project a PipelineStatusResponse into PhaseTimelineStep[]
 * for consumption by the PhaseTimeline presentational component.
 */
export function usePhaseTimeline(
  status: PipelineStatusResponse | undefined,
): PhaseTimelineStep[] {
  return useMemo(() => {
    if (!status) return [];

    return status.phases.map((phase) => ({
      phaseId: phase.phase_id,
      label: PHASE_LABELS[phase.phase_id] ?? phase.phase_id,
      status: phase.status,
      duration: phase.duration_seconds,
    }));
  }, [status]);
}
