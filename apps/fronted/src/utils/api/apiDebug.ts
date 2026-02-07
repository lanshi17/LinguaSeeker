/**
 * API 连接诊断工具
 * 用于调试前后端连接问题
 */

import { API_BASE_URL } from '../../services/api';

export interface ConnectionCheckResult {
  ok: boolean;
  status?: number;
  statusText?: string;
  latency?: number;
  error?: string;
  hint?: string;
}

/**
 * 检测后端服务是否运行
 */
export async function checkBackendRunning(): Promise<ConnectionCheckResult> {
  const startTime = performance.now();
  
  try {
    // 尝试访问后端根路径（不含 /api）
    const response = await fetch('http://localhost:8000/', {
      method: 'GET',
      signal: AbortSignal.timeout(3000),
    });
    
    const latency = Math.round(performance.now() - startTime);
    
    return {
      ok: response.ok,
      status: response.status,
      latency,
    };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : '连接失败',
      hint: '后端服务未启动，请运行: uvicorn main:app --reload --port 8000',
    };
  }
}

/**
 * 检测 API 连接状态
 */
export async function checkApiConnection(): Promise<ConnectionCheckResult> {
  const startTime = performance.now();
  
  try {
    // 尝试访问 API 健康检查端点或文档
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });
    
    const latency = Math.round(performance.now() - startTime);
    
    return {
      ok: response.ok,
      status: response.status,
      statusText: response.statusText,
      latency,
    };
  } catch (error) {
    // 尝试检查后端是否运行
    const backendCheck = await checkBackendRunning();
    
    if (!backendCheck.ok) {
      return {
        ok: false,
        error: '无法连接到后端服务',
        hint: '请确保后端服务已启动在 http://localhost:8000',
      };
    }
    
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'API 连接失败',
      hint: '后端服务正在运行，但 API 端点可能配置错误',
    };
  }
}

/**
 * 检测特定的 API 端点
 */
export async function checkApiEndpoint(endpoint: string): Promise<ConnectionCheckResult> {
  const startTime = performance.now();
  
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });
    
    const latency = Math.round(performance.now() - startTime);
    
    return {
      ok: response.ok,
      status: response.status,
      statusText: response.statusText,
      latency,
    };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : '请求失败',
    };
  }
}

/**
 * 获取 API 配置信息
 */
export function getApiConfig(): {
  baseUrl: string;
  mode: string;
  isDev: boolean;
  backendUrl: string;
} {
  return {
    baseUrl: API_BASE_URL,
    mode: import.meta.env.MODE,
    isDev: import.meta.env.DEV,
    backendUrl: 'http://localhost:8000',
  };
}

/**
 * 完整的诊断检查
 */
export async function runFullDiagnostics(): Promise<{
  summary: string;
  checks: Array<{ name: string; status: 'ok' | 'error' | 'warning'; message: string }>;
  recommendations: string[];
}> {
  const checks: Array<{ name: string; status: 'ok' | 'error' | 'warning'; message: string }> = [];
  const recommendations: string[] = [];
  
  const config = getApiConfig();
  checks.push({
    name: '配置检查',
    status: 'ok',
    message: `API 基础地址: ${config.baseUrl}, 模式: ${config.mode}`,
  });
  
  // 1. 检查后端是否运行
  const backendCheck = await checkBackendRunning();
  if (backendCheck.ok) {
    checks.push({
      name: '后端服务',
      status: 'ok',
      message: `后端服务运行正常 (${backendCheck.latency}ms)`,
    });
  } else {
    checks.push({
      name: '后端服务',
      status: 'error',
      message: backendCheck.error || '未运行',
    });
    recommendations.push('启动后端服务: cd backend && uvicorn main:app --reload --port 8000');
  }
  
  // 2. 检查 API 连接
  const apiCheck = await checkApiConnection();
  if (apiCheck.ok) {
    checks.push({
      name: 'API 连接',
      status: 'ok',
      message: `API 连接正常 (${apiCheck.latency}ms)`,
    });
  } else {
    checks.push({
      name: 'API 连接',
      status: 'error',
      message: apiCheck.error || '连接失败',
    });
    if (apiCheck.hint) {
      recommendations.push(apiCheck.hint);
    }
  }
  
  // 3. 检查关键端点
  const endpoints = ['/pdf/upload', '/pdf/fetch-by-pmid', '/tasks/test'];
  for (const endpoint of endpoints) {
    const result = await checkApiEndpoint(endpoint);
    if (result.ok || result.status === 405) {  // 405 Method Not Allowed 表示端点存在
      checks.push({
        name: `端点 ${endpoint}`,
        status: 'ok',
        message: `端点可访问 (状态: ${result.status})`,
      });
    } else if (result.status === 404) {
      checks.push({
        name: `端点 ${endpoint}`,
        status: 'warning',
        message: `端点返回 404`,
      });
    } else {
      checks.push({
        name: `端点 ${endpoint}`,
        status: 'error',
        message: `状态: ${result.status} ${result.statusText}`,
      });
    }
  }
  
  // 生成总结
  const errorCount = checks.filter(c => c.status === 'error').length;
  const warningCount = checks.filter(c => c.status === 'warning').length;
  
  let summary: string;
  if (errorCount === 0 && warningCount === 0) {
    summary = '所有检查通过，系统运行正常';
  } else if (errorCount === 0) {
    summary = `发现 ${warningCount} 个警告，建议查看`;
  } else {
    summary = `发现 ${errorCount} 个错误，${warningCount} 个警告，需要修复`;
  }
  
  return { summary, checks, recommendations };
}

/**
 * 打印诊断信息到控制台
 */
export async function printDiagnostics(): Promise<void> {
  console.group('🔧 API 连接诊断报告');
  console.log('运行时间:', new Date().toLocaleString());
  console.log('');
  
  const { summary, checks, recommendations } = await runFullDiagnostics();
  
  console.log('【总结】', summary);
  console.log('');
  
  console.log('【详细检查】');
  checks.forEach(check => {
    const icon = check.status === 'ok' ? '✅' : check.status === 'warning' ? '⚠️' : '❌';
    console.log(`${icon} ${check.name}: ${check.message}`);
  });
  
  if (recommendations.length > 0) {
    console.log('');
    console.log('【修复建议】');
    recommendations.forEach((rec, idx) => {
      console.log(`${idx + 1}. ${rec}`);
    });
  }
  
  console.groupEnd();
}

/**
 * 快速检查（用于组件显示）
 */
export async function quickCheck(): Promise<{
  connected: boolean;
  message: string;
  latency?: number;
}> {
  const result = await checkBackendRunning();
  
  if (result.ok) {
    const apiResult = await checkApiConnection();
    return {
      connected: apiResult.ok,
      message: apiResult.ok ? '已连接' : '后端运行但 API 错误',
      latency: apiResult.latency || result.latency,
    };
  }
  
  return {
    connected: false,
    message: '未连接',
  };
}
