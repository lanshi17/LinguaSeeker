/**
 * API client for document text-span annotations.
 *
 * Endpoints (mounted under /api/v1/documents):
 *   GET    /{sourceDocumentId}/annotations?track=...
 *   POST   /{sourceDocumentId}/annotations
 *   PATCH  /{sourceDocumentId}/annotations/{annotationId}
 *   DELETE /{sourceDocumentId}/annotations/{annotationId}
 */
import { apiClient } from "@/lib/api/client";
import type {
  AnnotationCreateRequest,
  AnnotationListResponse,
  AnnotationTrack,
  AnnotationUpdateRequest,
  UserAnnotation,
} from "@/features/evidence-search/types/annotations";

export async function listAnnotations(
  sourceDocumentId: string,
  track?: AnnotationTrack,
): Promise<UserAnnotation[]> {
  const params: Record<string, string> = {};
  if (track) params.track = track;
  const { data } = await apiClient.get<AnnotationListResponse>(
    `/documents/${encodeURIComponent(sourceDocumentId)}/annotations`,
    { params },
  );
  return data.items;
}

export async function createAnnotation(
  sourceDocumentId: string,
  payload: AnnotationCreateRequest,
): Promise<UserAnnotation> {
  const { data } = await apiClient.post<UserAnnotation>(
    `/documents/${encodeURIComponent(sourceDocumentId)}/annotations`,
    payload,
  );
  return data;
}

export async function updateAnnotation(
  sourceDocumentId: string,
  annotationId: string,
  payload: AnnotationUpdateRequest,
): Promise<UserAnnotation> {
  const { data } = await apiClient.patch<UserAnnotation>(
    `/documents/${encodeURIComponent(sourceDocumentId)}/annotations/${encodeURIComponent(annotationId)}`,
    payload,
  );
  return data;
}

export async function deleteAnnotation(
  sourceDocumentId: string,
  annotationId: string,
): Promise<void> {
  await apiClient.delete(
    `/documents/${encodeURIComponent(sourceDocumentId)}/annotations/${encodeURIComponent(annotationId)}`,
  );
}
