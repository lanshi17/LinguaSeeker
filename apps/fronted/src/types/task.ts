/**
 * 任务相关类型定义
 */

// 任务状态
export const TaskStatus = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;

export type TaskStatusValue = typeof TaskStatus[keyof typeof TaskStatus];

// 任务类型
export const TaskType = {
  PDF_UPLOAD: 'pdf_upload',
  PMID_FETCH: 'pmid_fetch',
  DOI_FETCH: 'doi_fetch',
  URL_FETCH: 'url_fetch',
} as const;

export type TaskTypeValue = typeof TaskType[keyof typeof TaskType];

// 任务项
export interface Task {
  id: string;
  type: TaskTypeValue;
  status: TaskStatusValue;
  title: string;
  description?: string;
  progress?: number;
  result?: {
    docId?: string;
    pmid?: string;
  };
  error?: string;
  createdAt: string;
  updatedAt: string;
}

// 输入类型
export const InputType = {
  PMID: 'pmid',
  DOI: 'doi',
  URL: 'url',
} as const;

export type InputTypeValue = typeof InputType[keyof typeof InputType];

// 输入解析结果
export interface ParsedInput {
  type: InputTypeValue;
  value: string;
  isValid: boolean;
}
