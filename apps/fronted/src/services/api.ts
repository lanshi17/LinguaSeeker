import {
  requestFormData,
  requestGetJson,
  requestJson,
} from './http';

import type {
  EvidenceSearchResponse,
  InteractionRespondRequest,
  InteractionRespondResponse,
  InteractionStartRequest,
  InteractionStartResponse,
  LogLinkReissueResponse,
  PubMedCandidateSearchRequest,
  PubMedCandidateSearchResponse,
  PubMedSelectionSubmitRequest,
  TaskRequestCreateResponse,
  TaskRequestStatusResponse,
  TaskFormStructured
} from '../types/api';

export function stringifyTaskForm(taskForm: TaskFormStructured) {
  return JSON.stringify(taskForm);
}

type ApiCallOptions = {
  signal?: AbortSignal;
};

export async function interactionStart(payload: InteractionStartRequest, options: ApiCallOptions = {}) {
  return requestJson<InteractionStartResponse>('/tasks/interaction/start', {
    method: 'POST',
    body: payload
  }, { signal: options.signal });
}

export async function interactionRespond(payload: InteractionRespondRequest, options: ApiCallOptions = {}) {
  return requestJson<InteractionRespondResponse>('/tasks/interaction/respond', {
    method: 'POST',
    body: payload
  }, { signal: options.signal });
}

export async function pubmedCandidateSearch(payload: PubMedCandidateSearchRequest, options: ApiCallOptions = {}) {
  return requestJson<PubMedCandidateSearchResponse>('/tasks/requests/pubmed/candidates', {
    method: 'POST',
    body: payload
  }, { signal: options.signal });
}

export async function pubmedSelectionSubmit(payload: PubMedSelectionSubmitRequest, options: ApiCallOptions = {}) {
  return requestJson<TaskRequestCreateResponse>('/tasks/requests/pubmed/submit', {
    method: 'POST',
    body: payload
  }, { signal: options.signal });
}

export async function uploadTaskRequest(taskForm: TaskFormStructured, files: File[], options: ApiCallOptions = {}) {
  const formData = new FormData();
  formData.append('task_form', stringifyTaskForm(taskForm));
  files.forEach((file) => {
    formData.append('files', file);
  });

  return requestFormData<TaskRequestCreateResponse>('/tasks/requests/upload', {
    method: 'POST',
    body: formData
  }, { signal: options.signal });
}

export async function getTaskRequestStatus(requestId: string, options: ApiCallOptions = {}) {
  return requestGetJson<TaskRequestStatusResponse>(`/tasks/requests/${encodeURIComponent(requestId)}`, { signal: options.signal });
}

export async function reissueLogLink(requestId: string, options: ApiCallOptions = {}) {
  const qs = new URLSearchParams({ request_id: requestId });
  return requestGetJson<LogLinkReissueResponse>(`/logs/reissue?${qs.toString()}`, { signal: options.signal });
}

export async function getEvidenceDocument(documentId: string, options: ApiCallOptions = {}) {
  return requestGetJson<EvidenceSearchResponse>(`/evidence/document/${encodeURIComponent(documentId)}`, {
    signal: options.signal
  });
}

export async function getEvidenceGraphStats(options: ApiCallOptions = {}) {
  return requestGetJson<EvidenceSearchResponse>('/evidence/graph/stats', {
    signal: options.signal
  });
}

export async function resyncEvidenceDocument(documentId: string, options: ApiCallOptions = {}) {
  return requestJson<EvidenceSearchResponse>(`/evidence/sync/document/${encodeURIComponent(documentId)}`, {
    method: 'POST'
  }, { signal: options.signal });
}
