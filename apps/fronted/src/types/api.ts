/**
 * API 类型定义
 * 根据 OpenAPI 3.1.0 规范生成
 */

// ==================== 枚举类型 ====================

/**
 * 任务状态枚举
 */
export const TaskStatusEnum = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export type TaskStatusValue = typeof TaskStatusEnum[keyof typeof TaskStatusEnum];

/**
 * 上传来源枚举
 */
export const UploadSource = {
  FILE: 'file',
  PMID: 'pmid',
  DOI: 'doi',
} as const;

export type UploadSourceValue = typeof UploadSource[keyof typeof UploadSource];

// ==================== 请求类型 ====================

/**
 * PDF 上传请求 (JSON + Base64)
 */
export interface PDFUploadRequest {
  /** Base64 编码的 PDF 文件内容 */
  file_content?: string | null;
  /** 原始文件名 */
  filename?: string | null;
  /** PubMed ID，用于自动获取文档 */
  pmid?: string | null;
  /** DOI，用于自动获取文档 */
  doi?: string | null;
  /** 文档上传来源 */
  source?: UploadSourceValue;
  /** 处理优先级 (0-10) */
  priority?: number | null;
}


/**
 * PMID 获取请求
 */
export interface FetchByPMIDRequest {
  /** PubMed ID */
  pmid: string;
  /** 处理优先级 (0-10) */
  priority?: number | null;
}

/**
 * DOI 获取请求
 */
export interface FetchByDOIRequest {
  /** DOI */
  doi: string;
  /** 处理优先级 (0-10) */
  priority?: number | null;
}

// ==================== 响应类型 ====================

/**
 * 证据项摘要
 */
export interface EvidenceItemSummary {
  /** 证据项唯一标识 */
  id: string;
  /** ACMG 证据代码 (如 PS1, PM2) */
  acmg_code: string;
  /** 置信度分数 (0.0-1.0) */
  confidence_score: number;
  /** 是否需要人工审核 (置信度 < 0.85) */
  review_required: boolean;
  /** 原始文档页码 */
  source_page: number;
}

/**
 * 任务状态响应
 */
export interface TaskStatusResponse {
  /** 解析任务唯一标识 */
  task_id: string;
  /** 关联文档唯一标识 */
  document_id: string;
  /** 当前任务状态 */
  status: TaskStatusValue;
  /** 进度百分比 (0-100) */
  progress_percentage: number;
  /** 当前处理阶段 */
  current_stage: string | null;
  /** 任务创建时间戳 */
  created_at: string;
  /** 任务最后更新时间戳 */
  updated_at: string;
  /** 任务完成时间戳 */
  completed_at: string | null;
  /** 任务失败时的错误信息 */
  error_message: string | null;
  /** 提取的证据项摘要列表 */
  evidence_items: EvidenceItemSummary[];
  /** 总处理时间 (秒) */
  processing_time_seconds: number | null;
  /** 原始文件大小 (字节) */
  file_size_bytes: number | null;
}

/**
 * 任务进度响应
 */
export interface TaskProgressResponse {
  task_id: string;
  progress_percentage: number;
  current_stage: string | null;
  status: TaskStatusValue;
}

/**
 * 通用 API 响应
 */
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

/**
 * 上传成功响应
 */
export interface UploadSuccessResponse {
  task_id: string;
  document_id?: string;
  status: TaskStatusValue;
  message?: string;
}

// ==================== 错误类型 ====================

/**
 * 验证错误项
 */
export interface ValidationError {
  /** 错误位置 */
  loc: (string | number)[];
  /** 错误信息 */
  msg: string;
  /** 错误类型 */
  type: string;
}

/**
 * HTTP 验证错误
 */
export interface HTTPValidationError {
  detail: ValidationError[];
}

// ==================== 文档解析结果类型 ====================

/**
 * 文档章节结构
 */
export interface DocumentSection {
  id: string;
  type: 'title' | 'abstract' | 'background' | 'objective' | 'methods' | 'results' | 'conclusion' | 'references' | 'other';
  title: string;
  content: string;
  level: number;
  order: number;
  pageNumber?: number;
}

/**
 * 文档解析结果
 */
export interface DocumentParseResult {
  document_id: string;
  pmid?: string;
  doi?: string;
  title: string;
  authors?: string[];
  abstract?: string;
  sections: DocumentSection[];
  evidence_items: EvidenceItemSummary[];
  images?: Array<{
    filename: string;
    url: string;
    caption?: string;
  }>;
  metadata: {
    journal?: string;
    publication_date?: string;
    keywords?: string[];
  };
}

// ==================== 任务管理类型 ====================

/**
 * 任务信息
 */
export interface TaskInfo {
  id: string;
  type: 'pdf_upload' | 'pmid_fetch' | 'doi_fetch';
  status: TaskStatusValue;
  title: string;
  description?: string;
  progress: number;
  currentStage?: string;
  result?: {
    documentId?: string;
    parseResult?: DocumentParseResult;
  };
  error?: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

/**
 * 任务列表过滤器
 */
export interface TaskFilter {
  status?: TaskStatusValue[];
  type?: string[];
  fromDate?: string;
  toDate?: string;
}
