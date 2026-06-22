/**
 * Shared type primitives used across feature modules.
 */

/** Processing run status shared across pipeline features. */
export type ProcessingStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

/** Phase identifier in the 3-phase pipeline. */
export type PhaseId = "phase_1" | "phase_2" | "phase_3";
