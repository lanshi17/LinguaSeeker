import type { RefObject } from "react";
import type { AnnotationTrack, UserAnnotation } from "../../types/annotations";
import type { FieldTypeOption } from "../../utils/fieldAssignment";

export interface TextNodeOffset {
  node: Text;
  start: number;
}

export interface OverlayRect {
  id: string;
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface SelectionInfo {
  start_offset: number;
  end_offset: number;
  rect: DOMRect;
  selectedText: string;
}

export type AnnotationOperation = void | Promise<void>;

export interface AnnotationCreatePayload {
  paragraph_id: string;
  track: AnnotationTrack;
  start_offset: number;
  end_offset: number;
  color: string;
}

export interface AnnotationUpdatePayload {
  color?: string | null;
  note?: string | null;
}

export interface AnnotationLayerProps {
  /** Ref to the container whose visible text the annotations anchor to. */
  containerRef: RefObject<HTMLDivElement | null>;
  paragraphId: string;
  track: AnnotationTrack;
  annotations: UserAnnotation[];
  /**
   * Dependency array trigger: recompute overlays when these change, for
   * example markdown/highlights that reshape the DOM.
   */
  recomputeDeps?: unknown[];
  onCreateAnnotation?: (payload: AnnotationCreatePayload) => AnnotationOperation;
  onUpdateAnnotation?: (
    id: string,
    payload: AnnotationUpdatePayload,
  ) => AnnotationOperation;
  onDeleteAnnotation?: (id: string) => AnnotationOperation;
  /**
   * When provided, the text-selection popup shows an "Assign to field" button
   * alongside annotation colors. The callback receives the selected text and
   * the target field type chosen by the user.
   */
  onAssignField?: (selectedText: string, fieldType: string) => AnnotationOperation;
  /** Available field types for the "Assign to field" dropdown. */
  fieldTypes?: FieldTypeOption[];
}
