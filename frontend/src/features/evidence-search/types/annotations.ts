/**
 * User-authored text-span annotations for bilingual document reading.
 *
 * Coordinate system: `start_offset`/`end_offset` are character offsets into
 * the paragraph's rendered visible text (flattened `textContent`), NOT into
 * the raw Markdown source. The backend stores offsets opaquely; the frontend
 * owns the coordinate mapping and must stay self-consistent.
 *
 * Field names are snake_case to match the backend API payload directly
 * (no client-side conversion layer), consistent with other evidence types.
 */

export type AnnotationTrack = "original" | "translated";

export interface UserAnnotation {
  id: string;
  source_document_id: string;
  track: AnnotationTrack;
  paragraph_id: string;
  start_offset: number;
  end_offset: number;
  color: string | null;
  note: string | null;
  author: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnnotationCreateRequest {
  track: AnnotationTrack;
  paragraph_id: string;
  start_offset: number;
  end_offset: number;
  color?: string | null;
  note?: string | null;
  author?: string | null;
}

export interface AnnotationUpdateRequest {
  color?: string | null;
  note?: string | null;
}

export interface AnnotationListResponse {
  items: UserAnnotation[];
}

/** Default palette offered in the annotation popover. */
export const ANNOTATION_COLORS = [
  "#fde68a", // amber
  "#bfdbfe", // blue
  "#bbf7d0", // green
  "#fbcfe8", // pink
  "#ddd6fe", // violet
  "#fed7aa", // orange
] as const;

/** Fallback color when an annotation has none. */
export const DEFAULT_ANNOTATION_COLOR = "#fde68a";
