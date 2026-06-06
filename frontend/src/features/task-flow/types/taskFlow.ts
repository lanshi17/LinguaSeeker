/** Entry mode for task creation. */
export type TaskFlowEntryMode = "local" | "online";

/** Structured task form fields. */
export interface TaskFormStructured {
  goal: string;
  disease: string;
  country?: string;
  language?: string;
  pmid?: string;
}

/** POST /tasks/interaction/start request. */
export interface InteractionStartRequest {
  task_form: TaskFormStructured;
}

/** POST /tasks/interaction/start response. */
export interface InteractionStartResponse {
  session_id: string;
  message: string;
  is_clarification: boolean;
}

/** POST /tasks/interaction/respond request. */
export interface InteractionRespondRequest {
  session_id: string;
  answer: string;
}

/** POST /tasks/interaction/respond response. */
export interface InteractionRespondResponse {
  message: string;
  is_clarification: boolean;
  task_form?: TaskFormStructured;
}
