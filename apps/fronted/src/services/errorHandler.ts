/**
 * 错误处理工具
 * 用于解析和分类 API 错误
 */

export type ErrorType = 'validation' | 'server' | 'network' | 'duplicate' | 'unknown';

export interface ParsedError {
  type: ErrorType;
  title: string;
  message: string;
  details?: string;
  action?: string;
  retryable: boolean;
}

/**
 * 解析 API 错误
 */
export function parseAPIError(error: unknown): ParsedError {
  // 处理自定义 APIError
  if (error instanceof Error) {
    const message = error.message;
    
    // 400 错误 - 请求参数问题
    if (message.includes('400') || message.includes('验证错误')) {
      return {
        type: 'validation',
        title: '请求参数错误',
        message: '上传的文件或参数不符合要求',
        details: extractDetail(message),
        action: '请检查文件是否为有效的 PDF 格式，且大小不超过限制',
        retryable: true,
      };
    }
    
    // 404 错误 - 端点不存在
    if (message.includes('404')) {
      return {
        type: 'server',
        title: 'API 端点不存在',
        message: '后端服务缺少必要的接口',
        details: message,
        action: '请联系管理员检查后端服务配置',
        retryable: false,
      };
    }
    
    // 422 错误 - 验证错误
    if (message.includes('422')) {
      return {
        type: 'validation',
        title: '数据验证失败',
        message: '提交的数据格式不正确',
        details: extractDetail(message),
        action: '请检查输入的数据格式',
        retryable: true,
      };
    }
    
    // 重复文件错误 - Document with hash already exists
    const lowerMsg = message.toLowerCase();
    if (lowerMsg.includes('already exists') || 
        lowerMsg.includes('document with hash') ||
        lowerMsg.includes('duplicate') ||
        message.includes('文件已存在') ||
        message.includes('文档已存在')) {
      return {
        type: 'duplicate',
        title: '文件已上传过',
        message: '此文件已在系统中存在，请勿重复上传',
        details: message,
        action: '查看已有文档 或 上传其他文件',
        retryable: false,
      };
    }
    
    // 500/502/503 错误 - 服务器问题
    if (message.includes('500') || message.includes('502') || message.includes('503')) {
      return {
        type: 'server',
        title: '服务器内部错误',
        message: '后端服务出现技术故障',
        details: message,
        action: '后端数据库可能存在问题，请稍后重试或联系管理员',
        retryable: true,
      };
    }
    
    // 连接错误
    if (message.includes('fetch') || message.includes('network') || message.includes('连接')) {
      return {
        type: 'network',
        title: '网络连接失败',
        message: '无法连接到后端服务',
        details: message,
        action: '请确保后端服务已启动（uvicorn main:app --reload --port 8000）',
        retryable: true,
      };
    }
  }
  
  // 未知错误
  return {
    type: 'unknown',
    title: '未知错误',
    message: '发生未知错误',
    details: error instanceof Error ? error.message : String(error),
    action: '请刷新页面重试',
    retryable: true,
  };
}

/**
 * 提取错误详情
 */
function extractDetail(message: string): string | undefined {
  // 尝试提取具体错误信息
  const detailMatch = message.match(/[:：]\s*(.+)$/);
  return detailMatch?.[1];
}

/**
 * 获取用户友好的错误提示
 */
export function getUserFriendlyError(error: unknown): {
  title: string;
  description: string;
  action: string;
  type: 'error' | 'warning' | 'info';
} {
  const parsed = parseAPIError(error);
  
  switch (parsed.type) {
    case 'validation':
      return {
        title: parsed.title,
        description: parsed.message,
        action: parsed.action || '请检查输入后重试',
        type: 'warning',
      };
    
    case 'duplicate':
      return {
        title: '文件已上传过',
        description: '此文件已在系统中存在，请勿重复上传',
        action: '查看已有文档 或 上传其他文件',
        type: 'warning',
      };
    
    case 'server':
      return {
        title: '服务暂时不可用',
        description: '后端服务器出现技术问题，可能是数据库连接失败',
        action: '请稍后重试，或联系技术支持',
        type: 'error',
      };
    
    case 'network':
      return {
        title: '连接失败',
        description: '无法连接到后端服务',
        action: '请确保后端服务已启动',
        type: 'error',
      };
    
    default:
      return {
        title: '操作失败',
        description: parsed.message,
        action: '请刷新页面后重试',
        type: 'error',
      };
  }
}

/**
 * 验证文件是否符合要求
 */
export function validatePDFFile(file: File): {
  valid: boolean;
  error?: string;
} {
  // 检查文件类型
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    return {
      valid: false,
      error: '文件必须是 PDF 格式',
    };
  }
  
  // 检查文件大小（限制 50MB）
  const maxSize = 50 * 1024 * 1024; // 50MB
  if (file.size > maxSize) {
    return {
      valid: false,
      error: `文件大小超过限制（最大 50MB，当前 ${(file.size / 1024 / 1024).toFixed(2)}MB）`,
    };
  }
  
  // 检查文件是否为空
  if (file.size === 0) {
    return {
      valid: false,
      error: '文件内容为空',
    };
  }
  
  return { valid: true };
}

/**
 * 验证 PMID 格式
 */
export function validatePMID(pmid: string): {
  valid: boolean;
  error?: string;
} {
  const trimmed = pmid.trim();
  
  if (!trimmed) {
    return { valid: false, error: 'PMID 不能为空' };
  }
  
  if (!/^\d+$/.test(trimmed)) {
    return { valid: false, error: 'PMID 必须是纯数字' };
  }
  
  if (trimmed.length > 20) {
    return { valid: false, error: 'PMID 长度异常' };
  }
  
  return { valid: true };
}

/**
 * 验证 DOI 格式
 */
export function validateDOI(doi: string): {
  valid: boolean;
  error?: string;
} {
  const trimmed = doi.trim();
  
  if (!trimmed) {
    return { valid: false, error: 'DOI 不能为空' };
  }
  
  if (!/^10\.\d{4,}\/.+/.test(trimmed)) {
    return { valid: false, error: 'DOI 格式不正确（应以 10. 开头）' };
  }
  
  return { valid: true };
}

export default {
  parseAPIError,
  getUserFriendlyError,
  validatePDFFile,
  validatePMID,
  validateDOI,
};
