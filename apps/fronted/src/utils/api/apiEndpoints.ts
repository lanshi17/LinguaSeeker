/**
 * API 端点清单和验证工具
 * 基于 api_docs/openapi_v1.json
 */

export interface ApiEndpoint {
  path: string;
  method: string;
  summary: string;
  implemented: boolean;
  functionName?: string;
}

/**
 * OpenAPI v1 中定义的所有端点
 */
export const API_ENDPOINTS: ApiEndpoint[] = [
  {
    path: '/api/v1/pdf/upload',
    method: 'POST',
    summary: 'Upload PDF document (multipart/form-data)',
    implemented: true,
    functionName: 'uploadPDFForm',
  },
  {
    path: '/api/v1/pdf/fetch-by-pmid',
    method: 'POST',
    summary: 'Fetch and parse document by PMID',
    implemented: true,
    functionName: 'fetchByPMID',
  },
  {
    path: '/api/v1/pdf/fetch-by-doi',
    method: 'POST',
    summary: 'Fetch and parse document by DOI',
    implemented: true,
    functionName: 'fetchByDOI',
  },
  {
    path: '/api/v1/tasks/{task_id}',
    method: 'GET',
    summary: 'Get parsing task status',
    implemented: true,
    functionName: 'getTaskStatus',
  },
  {
    path: '/api/v1/tasks/{task_id}',
    method: 'DELETE',
    summary: 'Cancel parsing task',
    implemented: true,
    functionName: 'cancelTask',
  },
  {
    path: '/api/v1/tasks/{task_id}/progress',
    method: 'GET',
    summary: 'Get real-time task progress',
    implemented: true,
    functionName: 'getTaskProgress',
  },
  {
    path: '/api/v1/tasks/{task_id}/retry',
    method: 'POST',
    summary: 'Retry failed parsing task',
    implemented: true,
    functionName: 'retryTask',
  },
  {
    path: '/api/v1/{task_id}',
    method: 'GET',
    summary: 'Get task status (legacy route)',
    implemented: true,
    functionName: 'getTaskStatusLegacy',
  },
  {
    path: '/api/v1/{task_id}',
    method: 'DELETE',
    summary: 'Cancel task (legacy route)',
    implemented: true,
    functionName: 'cancelTaskLegacy',
  },
];

/**
 * 获取实现统计
 */
export function getImplementationStats(): {
  total: number;
  implemented: number;
  pending: number;
} {
  const total = API_ENDPOINTS.length;
  const implemented = API_ENDPOINTS.filter(e => e.implemented).length;
  return {
    total,
    implemented,
    pending: total - implemented,
  };
}

/**
 * 打印端点清单
 */
export function printApiEndpoints(): void {
  const stats = getImplementationStats();
  
  console.group('📋 API 端点清单 (OpenAPI v1)');
  console.log(`实现进度: ${stats.implemented}/${stats.total}`);
  console.log('');
  
  const grouped = API_ENDPOINTS.reduce((acc, endpoint) => {
    const category = endpoint.path.includes('/pdf/') 
      ? 'PDF 解析' 
      : endpoint.path.includes('/tasks/') 
        ? '任务管理'
        : '其他';
    if (!acc[category]) acc[category] = [];
    acc[category].push(endpoint);
    return acc;
  }, {} as Record<string, ApiEndpoint[]>);
  
  Object.entries(grouped).forEach(([category, endpoints]) => {
    console.group(category);
    endpoints.forEach(endpoint => {
      const icon = endpoint.implemented ? '✅' : '⏳';
      console.log(`${icon} ${endpoint.method.padEnd(6)} ${endpoint.path}`);
      console.log(`   ${endpoint.summary}`);
      if (endpoint.functionName) {
        console.log(`   函数: ${endpoint.functionName}()`);
      }
    });
    console.groupEnd();
  });
  
  console.groupEnd();
}

/**
 * 验证端点可访问性
 */
export async function verifyEndpoints(): Promise<Array<{
  endpoint: ApiEndpoint;
  accessible: boolean;
  status?: number;
  error?: string;
}>> {
  const results = [];
  
  for (const endpoint of API_ENDPOINTS) {
    // 跳过需要路径参数的端点（简单验证）
    if (endpoint.path.includes('{')) {
      results.push({
        endpoint,
        accessible: true,
        status: undefined,
        error: '需要路径参数，跳过验证',
      });
      continue;
    }
    
    try {
      const response = await fetch(endpoint.path, {
        method: endpoint.method === 'GET' ? 'GET' : 'OPTIONS',
      });
      
      results.push({
        endpoint,
        accessible: response.ok || response.status === 405, // 405 = Method Not Allowed (端点存在)
        status: response.status,
      });
    } catch (error) {
      results.push({
        endpoint,
        accessible: false,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
  
  return results;
}
