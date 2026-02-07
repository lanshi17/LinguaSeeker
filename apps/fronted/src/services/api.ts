/**
 * API 服务
 * 基于 OpenAPI 3.1.0 规范实现
 * Base URL: /api/v1
 */

import type {
  TaskStatusResponse,
  TaskProgressResponse,
  UploadSuccessResponse,
  PDFUploadRequest,
  FetchByPMIDRequest,
  FetchByDOIRequest,
  ApiResponse,
  ValidationError,
} from '../types';

// 从环境变量获取 API 基础 URL，默认为 /api/v1
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/**
 * API 错误类
 */
export class APIError extends Error {
  statusCode?: number;
  validationErrors?: ValidationError[];
  errorType?: 'duplicate' | 'validation' | 'server' | 'network' | 'unknown';
  
  constructor(
    message: string,
    statusCode?: number,
    validationErrors?: ValidationError[],
    errorType?: 'duplicate' | 'validation' | 'server' | 'network' | 'unknown'
  ) {
    super(message);
    this.name = 'APIError';
    this.statusCode = statusCode;
    this.validationErrors = validationErrors;
    this.errorType = errorType;
  }
}

/**
 * 处理 API 响应
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData: { message?: string; error?: string; detail?: ValidationError[]; hint?: string } = {};
    
    try {
      errorData = await response.json();
    } catch {
      // 如果解析 JSON 失败，使用状态文本
      errorData = { message: response.statusText };
    }
    
    // 构建错误消息（只使用字符串类型的字段）
    let errorMessage = errorData.message || errorData.error || `API 错误: ${response.status}`;
    const fullErrorText = JSON.stringify(errorData).toLowerCase();
    
    // 针对不同状态码的特殊处理
    if (response.status === 500) {
      // 检查是否是重复文件错误（优先检查，避免显示"服务器内部错误"）
      if (fullErrorText.includes('already exists') ||
          fullErrorText.includes('document with hash') ||
          errorMessage.toLowerCase().includes('already exists') ||
          errorMessage.toLowerCase().includes('document with hash')) {
        console.warn('[API] 检测到重复文件上传:', errorData);
        throw new APIError(
          `文件已存在: ${errorMessage}`,
          409, // 使用 409 Conflict 语义
          undefined,
          'duplicate'
        );
      }
      
      errorMessage = `服务器内部错误: ${errorMessage}`;
      if (errorData.hint) {
        errorMessage += ` (${errorData.hint})`;
      }
    } else if (response.status === 404) {
      errorMessage = `API 端点不存在: ${errorMessage}`;
    } else if (response.status === 422 && errorData.detail) {
      throw new APIError(
        '验证错误: ' + errorData.detail.map(d => d.msg).join(', '),
        response.status,
        errorData.detail
      );
    }
    
    throw new APIError(errorMessage, response.status);
  }
  
  return response.json() as Promise<T>;
}

// ==================== PDF 解析 API ====================

/**
 * 上传 PDF 文档 (multipart/form-data)
 * POST /api/v1/pdf/upload
 *
 * @param file PDF文件
 * @param priority 优先级
 * @param force 是否强制上传（绕过重复检测）
 * @param clientHash 前端计算的hash（用于调试对比）
 */
export async function uploadPDFForm(
  file: File,
  priority: number = 0,
  force: boolean = false,
  clientHash?: string
): Promise<UploadSuccessResponse> {
  const url = new URL(`${API_BASE_URL}/pdf/upload`, window.location.origin);
  if (force) {
    url.searchParams.append('force', 'true');
  }

  const formData = new FormData();
  formData.append('file', file);
  formData.append('priority', priority.toString());
  if (clientHash) {
    formData.append('client_hash', clientHash);
  }

  console.log('[API] FormData上传:', {
    filename: file.name,
    size: file.size,
    force,
    clientHash: clientHash ? `${clientHash.slice(0, 16)}...` : undefined,
  });

  const response = await fetch(url.toString(), {
    method: 'POST',
    body: formData,
  });

  return handleResponse<UploadSuccessResponse>(response);
}

/**
 * 通过 PMID 获取并解析文档
 * POST /api/v1/pdf/fetch-by-pmid
 */
export async function fetchByPMID(
  request: FetchByPMIDRequest
): Promise<UploadSuccessResponse> {
  const params = new URLSearchParams();
  params.append('pmid', request.pmid);
  if (request.priority !== undefined && request.priority !== null) {
    params.append('priority', request.priority.toString());
  }
  
  const response = await fetch(`${API_BASE_URL}/pdf/fetch-by-pmid?${params}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  return handleResponse<UploadSuccessResponse>(response);
}

/**
 * 通过 DOI 获取并解析文档
 * POST /api/v1/pdf/fetch-by-doi
 */
export async function fetchByDOI(
  request: FetchByDOIRequest
): Promise<UploadSuccessResponse> {
  const params = new URLSearchParams();
  params.append('doi', request.doi);
  if (request.priority !== undefined && request.priority !== null) {
    params.append('priority', request.priority.toString());
  }
  
  const response = await fetch(`${API_BASE_URL}/pdf/fetch-by-doi?${params}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  return handleResponse<UploadSuccessResponse>(response);
}

// ==================== 任务管理 API ====================

/**
 * 获取任务状态
 * GET /api/v1/tasks/{task_id}
 */
export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/tasks/${encodeURIComponent(taskId)}`);
  return handleResponse<TaskStatusResponse>(response);
}

/**
 * 取消任务
 * DELETE /api/v1/tasks/{task_id}
 */
export async function cancelTask(taskId: string): Promise<ApiResponse> {
  const response = await fetch(`${API_BASE_URL}/tasks/${encodeURIComponent(taskId)}`, {
    method: 'DELETE',
  });
  return handleResponse<ApiResponse>(response);
}

/**
 * 获取任务实时进度
 * GET /api/v1/tasks/{task_id}/progress
 */
export async function getTaskProgress(taskId: string): Promise<TaskProgressResponse> {
  const response = await fetch(`${API_BASE_URL}/tasks/${encodeURIComponent(taskId)}/progress`);
  return handleResponse<TaskProgressResponse>(response);
}

/**
 * 重试失败的任务
 * POST /api/v1/tasks/{task_id}/retry
 */
export async function retryTask(taskId: string): Promise<ApiResponse> {
  const response = await fetch(`${API_BASE_URL}/tasks/${encodeURIComponent(taskId)}/retry`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  return handleResponse<ApiResponse>(response);
}

// ==================== 遗留/简写路由 ====================

/**
 * 获取任务状态（简写形式）
 * GET /api/v1/{task_id}
 * 注意：这是遗留路由，建议使用 /api/v1/tasks/{task_id}
 */
export async function getTaskStatusLegacy(taskId: string): Promise<TaskStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/${encodeURIComponent(taskId)}`);
  return handleResponse<TaskStatusResponse>(response);
}

/**
 * 取消任务（简写形式）
 * DELETE /api/v1/{task_id}
 * 注意：这是遗留路由，建议使用 /api/v1/tasks/{task_id}
 */
export async function cancelTaskLegacy(taskId: string): Promise<ApiResponse> {
  const response = await fetch(`${API_BASE_URL}/${encodeURIComponent(taskId)}`, {
    method: 'DELETE',
  });
  return handleResponse<ApiResponse>(response);
}

// ==================== 文档 API (兼容旧版本) ====================

/**
 * 获取文档内容
 * GET /api/v1/documents/{document_id}
 */
export async function getDocument(documentId: string): Promise<ApiResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(documentId)}`);
  return handleResponse<ApiResponse>(response);
}

/**
 * 获取文档图片
 * GET /api/v1/documents/{document_id}/images/{filename}
 */
export function getDocumentImageUrl(documentId: string, filename: string): string {
  return `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/images/${encodeURIComponent(filename)}`;
}

// ==================== 轮询工具 ====================

/**
 * 轮询任务状态直到完成或失败
 * @param taskId 任务ID
 * @param onProgress 进度回调
 * @param interval 轮询间隔 (ms)
 * @param maxAttempts 最大尝试次数
 */
export async function pollTaskStatus(
  taskId: string,
  onProgress?: (status: TaskStatusResponse) => void,
  interval: number = 2000,
  maxAttempts: number = 300
): Promise<TaskStatusResponse> {
  let attempts = 0;
  
  return new Promise((resolve, reject) => {
    const poll = async () => {
      attempts++;
      
      if (attempts > maxAttempts) {
        reject(new APIError('轮询超时'));
        return;
      }
      
      try {
        const status = await getTaskStatus(taskId);
        onProgress?.(status);
        
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
          resolve(status);
          return;
        }
        
        setTimeout(poll, interval);
      } catch (error) {
        reject(error);
      }
    };
    
    poll();
  });
}

/**
 * 创建 AbortController 用于取消轮询
 */
export function createTaskPoller() {
  const abortController = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  
  const poll = async (
    taskId: string,
    onProgress?: (status: TaskStatusResponse) => void,
    interval: number = 2000
  ): Promise<TaskStatusResponse> => {
    return new Promise((resolve, reject) => {
      const doPoll = async () => {
        if (abortController.signal.aborted) {
          reject(new APIError('轮询已取消'));
          return;
        }
        
        try {
          const status = await getTaskStatus(taskId);
          onProgress?.(status);
          
          if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
            resolve(status);
            return;
          }
          
          timeoutId = setTimeout(doPoll, interval);
        } catch (error) {
          reject(error);
        }
      };
      
      doPoll();
    });
  };
  
  const abort = () => {
    abortController.abort();
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  };
  
  return { poll, abort };
}

// ==================== WebSocket 导出 ====================

export {
  TaskWebSocketClient,
  createTaskWebSocket,
  watchTaskWithWebSocket,
} from './websocket';

export type {
  WebSocketMessage,
  WebSocketStatus,
  WebSocketOptions,
} from './websocket';

// ==================== 默认导出 ====================

export default {
  uploadPDFForm,
  fetchByPMID,
  fetchByDOI,
  getTaskStatus,
  cancelTask,
  getTaskProgress,
  retryTask,
  getTaskStatusLegacy,
  cancelTaskLegacy,
  getDocument,
  getDocumentImageUrl,
  pollTaskStatus,
  createTaskPoller,
};
