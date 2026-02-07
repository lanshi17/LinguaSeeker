/**
 * API 健康检查工具
 * 验证所有业务端点的可用性
 */

import { API_BASE_URL } from '../../services/api';

export interface EndpointCheck {
  name: string;
  method: string;
  path: string;
  expectedStatus: number[];
  result?: {
    status: number;
    statusText: string;
    ok: boolean;
    duration: number;
    error?: string;
  };
}

/**
 * 定义所有业务端点
 */
const BUSINESS_ENDPOINTS: EndpointCheck[] = [
  {
    name: 'PDF 上传 (Base64)',
    method: 'OPTIONS',
    path: `${API_BASE_URL}/pdf/upload`,
    expectedStatus: [200, 405],
  },
  {
    name: 'PDF 上传 (FormData)',
    method: 'OPTIONS',
    path: `${API_BASE_URL}/pdf/upload`,
    expectedStatus: [200, 405],
  },
  {
    name: 'PMID 获取',
    method: 'OPTIONS',
    path: `${API_BASE_URL}/pdf/fetch-by-pmid?pmid=123`,
    expectedStatus: [200, 405],
  },
  {
    name: 'DOI 获取',
    method: 'OPTIONS',
    path: `${API_BASE_URL}/pdf/fetch-by-doi?doi=10.1000/test`,
    expectedStatus: [200, 405],
  },
  {
    name: '任务状态查询',
    method: 'GET',
    path: `${API_BASE_URL}/tasks/test-task-id`,
    expectedStatus: [200, 404], // 404 表示端点存在但任务不存在
  },
  {
    name: '任务进度查询',
    method: 'GET',
    path: `${API_BASE_URL}/tasks/test-task-id/progress`,
    expectedStatus: [200, 404],
  },
  {
    name: '健康检查',
    method: 'GET',
    path: `${API_BASE_URL}/health`,
    expectedStatus: [200],
  },
];

/**
 * 检查单个端点
 */
async function checkEndpoint(endpoint: EndpointCheck): Promise<EndpointCheck> {
  const start = performance.now();
  
  try {
    const response = await fetch(endpoint.path, {
      method: endpoint.method,
      cache: 'no-cache',
    });
    
    const duration = Math.round(performance.now() - start);
    const isExpected = endpoint.expectedStatus.includes(response.status);
    
    return {
      ...endpoint,
      result: {
        status: response.status,
        statusText: response.statusText,
        ok: isExpected,
        duration,
      },
    };
  } catch (error) {
    return {
      ...endpoint,
      result: {
        status: 0,
        statusText: 'Error',
        ok: false,
        duration: Math.round(performance.now() - start),
        error: error instanceof Error ? error.message : 'Unknown error',
      },
    };
  }
}

/**
 * 运行完整健康检查
 */
export async function runHealthCheck(): Promise<{
  summary: { total: number; passed: number; failed: number };
  results: EndpointCheck[];
}> {
  console.group('🏥 API 健康检查');
  
  const results: EndpointCheck[] = [];
  
  for (const endpoint of BUSINESS_ENDPOINTS) {
    const result = await checkEndpoint(endpoint);
    results.push(result);
    
    const icon = result.result?.ok ? '✅' : '❌';
    const status = result.result?.status || 'ERR';
    console.log(`${icon} ${result.name} (${result.method}) - HTTP ${status} (${result.result?.duration}ms)`);
  }
  
  const passed = results.filter(r => r.result?.ok).length;
  const failed = results.length - passed;
  
  console.log('');
  console.log(`总结: ${passed}/${results.length} 通过, ${failed} 失败`);
  console.groupEnd();
  
  return {
    summary: { total: results.length, passed, failed },
    results,
  };
}

/**
 * 快速检查关键端点
 */
export async function quickHealthCheck(): Promise<{
  ok: boolean;
  pdfUpload: boolean;
  taskStatus: boolean;
  health: boolean;
}> {
  const checks = await Promise.all([
    fetch(`${API_BASE_URL}/pdf/upload`, { method: 'OPTIONS' })
      .then(r => r.status === 405 || r.ok)
      .catch(() => false),
    fetch(`${API_BASE_URL}/tasks/test`, { method: 'GET' })
      .then(r => r.status === 404) // 404 表示端点存在
      .catch(() => false),
    fetch(`${API_BASE_URL}/health`, { method: 'GET' })
      .then(r => r.ok)
      .catch(() => false),
  ]);
  
  return {
    ok: checks.every(c => c),
    pdfUpload: checks[0],
    taskStatus: checks[1],
    health: checks[2],
  };
}

/**
 * 诊断 PDF 上传问题
 */
export async function diagnosePDFUpload(): Promise<{
  canConnect: boolean;
  endpointExists: boolean;
  postWorks: boolean;
  error?: string;
}> {
  try {
    // 1. 检查 OPTIONS 是否支持
    const optionsRes = await fetch(`${API_BASE_URL}/pdf/upload`, {
      method: 'OPTIONS',
    });
    
    if (!optionsRes.ok && optionsRes.status !== 405) {
      return {
        canConnect: false,
        endpointExists: false,
        postWorks: false,
        error: `OPTIONS 失败: ${optionsRes.status}`,
      };
    }
    
    // 2. 尝试发送空表单（会失败但验证端点）
    const formData = new FormData();
    formData.append('file', new Blob(['test'], { type: 'application/pdf' }), 'test.pdf');
    
    const postRes = await fetch(`${API_BASE_URL}/pdf/upload`, {
      method: 'POST',
      body: formData,
    });
    
    // 400 表示请求格式有问题（预期内）
    // 422 表示验证错误（预期内）
    // 500 表示服务器错误
    
    return {
      canConnect: true,
      endpointExists: true,
      postWorks: postRes.status !== 500 && postRes.status !== 404,
      error: postRes.status >= 500 ? `服务器错误: ${postRes.status}` : undefined,
    };
  } catch (error) {
    return {
      canConnect: false,
      endpointExists: false,
      postWorks: false,
      error: error instanceof Error ? error.message : '连接失败',
    };
  }
}

// 导出到全局
if (typeof window !== 'undefined') {
  (window as unknown as Record<string, unknown>).healthCheck = {
    runHealthCheck,
    quickHealthCheck,
    diagnosePDFUpload,
  };
}
