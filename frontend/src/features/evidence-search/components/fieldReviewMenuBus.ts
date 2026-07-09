import type { MouseEvent as ReactMouseEvent } from "react";

export interface FieldReviewInfo {
  evidenceId: string;
  fieldId: string;
  label: string;
  category?: string | null;
  currentStatus: string;
  value?: string | null;
  groupId: string;
}

export type ReviewContextMap = Map<string, FieldReviewInfo>;

export type FieldReviewMenuState = {
  x: number;
  y: number;
  info: FieldReviewInfo;
} | null;

type FieldReviewMenuEvent = Pick<
  ReactMouseEvent | MouseEvent,
  "clientX" | "clientY" | "preventDefault" | "stopPropagation"
>;

let menuHandler: ((state: FieldReviewMenuState) => void) | null = null;

export function setFieldReviewMenuHandler(
  handler: ((state: FieldReviewMenuState) => void) | null,
): void {
  menuHandler = handler;
}

/** Call from any <mark>'s onClick to open the review menu. */
export function openFieldReviewMenu(
  e: FieldReviewMenuEvent,
  info: FieldReviewInfo,
): void {
  e.preventDefault();
  e.stopPropagation();
  menuHandler?.({ x: e.clientX, y: e.clientY, info });
}
