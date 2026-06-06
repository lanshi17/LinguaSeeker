import { apiClient } from "@/lib/api/client";
import type {
  InteractionStartRequest,
  InteractionStartResponse,
  InteractionRespondRequest,
  InteractionRespondResponse,
} from "../types/taskFlow";

export async function interactionStart(
  body: InteractionStartRequest,
): Promise<InteractionStartResponse> {
  const { data } = await apiClient.post<InteractionStartResponse>(
    "/tasks/interaction/start",
    body,
  );
  return data;
}

export async function interactionRespond(
  body: InteractionRespondRequest,
): Promise<InteractionRespondResponse> {
  const { data } = await apiClient.post<InteractionRespondResponse>(
    "/tasks/interaction/respond",
    body,
  );
  return data;
}

export async function confirmTaskForm(sessionId: string): Promise<void> {
  await apiClient.post("/tasks/interaction/confirm", {
    session_id: sessionId,
  });
}

export async function uploadRequest(formData: FormData): Promise<void> {
  await apiClient.post("/tasks/requests/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}
