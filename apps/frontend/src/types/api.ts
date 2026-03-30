export type TaskFormStructured = {
  goal: string;
  disease: string;
  country: string;
  language: string;
};

export type InteractionStartRequest = {
  user_input: string;
};

export type InteractionStartResponse = {
  session_id: string;
  ready: boolean;
  task_form: TaskFormStructured | null;
  question: string | null;
  round: number;
  needs_clarification?: boolean | null;
  clarification_question?: string | null;
};

export type InteractionRespondRequest = {
  session_id: string;
  user_response: string;
};

export type InteractionRespondResponse = {
  ready: boolean;
  task_form: TaskFormStructured | null;
  question: string | null;
  round: number;
  task_form_ready?: boolean | null;
  request_payload?: Record<string, unknown> | null;
  task_form_payload?: Record<string, unknown> | null;
};

export type BranchOption = {
  source: string;
};

export type ConfirmationContractRequest = {
  task_form_payload: Record<string, unknown>;
};

export type ConfirmationContractResponse = {
  confirmed: boolean;
  request_id: string;
  available_branches: BranchOption[];
};

export type PubMedCandidateItem = {
  pmid: string;
  title: string;
  journal: string;
  pub_date: string;
};

export type PubMedCandidateSearchRequest = {
  request_id?: string;
  task_form?: string;
  target: string;
  disease: string;
  country?: string;
  language?: string;
  source?: string;
  candidate_limit?: number;
};

export type PubMedCandidateSearchResponse = {
  request_id?: string;
  task_form: string;
  candidates: PubMedCandidateItem[];
};

export type PubMedSelectionSubmitRequest = {
  request_id?: string;
  task_form?: string;
  selected_pmids: string[];
  target: string;
  disease: string;
  country?: string;
  language?: string;
  source?: string;
};

export type PaperTaskItemResponse = {
  paper_task_id: string;
  filename?: string | null;
  status: string;
  error_code?: string | null;
  duplicate_of?: string | null;
  document_id?: string | null;
  celery_task_id?: string | null;
};

export type TaskRequestCreateResponse = {
  request_id: string;
  status: string;
  papers?: PaperTaskItemResponse[];
};

export type TaskRequestStatusResponse = {
  request_id: string;
  status: string;
  papers?: PaperTaskItemResponse[];
};

export type LogLinkReissueResponse = {
  request_id: string;
  log_link: string;
  expires_in_seconds?: number;
};

export type EvidenceSearchResponse = {
  code: number;
  message: string;
  data: unknown;
};

export type ErrorResponse = {
  detail: string;
};

export type ValidationError = {
  loc: unknown[];
  msg: string;
  type: string;
};

export type HTTPValidationError = {
  detail?: ValidationError[];
};
