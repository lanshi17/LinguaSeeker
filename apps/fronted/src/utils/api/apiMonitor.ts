/**
 * API 监控工具
 * 用于监控 API 响应时间和错误率
 */

interface APICall {
  endpoint: string;
  method: string;
  startTime: number;
  endTime?: number;
  status?: number;
  error?: string;
  duration?: number;
}

interface APIMetrics {
  totalCalls: number;
  successCalls: number;
  errorCalls: number;
  avgResponseTime: number;
  slowestEndpoint: string;
  fastestEndpoint: string;
  errorRate: number;
}

class APIMonitor {
  private calls: APICall[] = [];
  private maxHistory = 100;

  /**
   * 开始记录 API 调用
   */
  startCall(endpoint: string, method: string): number {
    const call: APICall = {
      endpoint,
      method,
      startTime: performance.now(),
    };
    this.calls.push(call);
    
    // 限制历史记录数量
    if (this.calls.length > this.maxHistory) {
      this.calls.shift();
    }
    
    return this.calls.length - 1;
  }

  /**
   * 结束记录 API 调用
   */
  endCall(index: number, status: number, error?: string): void {
    const call = this.calls[index];
    if (call) {
      call.endTime = performance.now();
      call.status = status;
      call.error = error;
      call.duration = call.endTime - call.startTime;
    }
  }

  /**
   * 获取统计数据
   */
  getMetrics(): APIMetrics {
    const completedCalls = this.calls.filter(c => c.duration !== undefined);
    
    if (completedCalls.length === 0) {
      return {
        totalCalls: 0,
        successCalls: 0,
        errorCalls: 0,
        avgResponseTime: 0,
        slowestEndpoint: '-',
        fastestEndpoint: '-',
        errorRate: 0,
      };
    }

    const successCalls = completedCalls.filter(c => c.status && c.status < 400);
    const errorCalls = completedCalls.filter(c => c.status && c.status >= 400);
    
    const durations = completedCalls.map(c => c.duration || 0);
    const avgResponseTime = durations.reduce((a, b) => a + b, 0) / durations.length;
    
    const sortedByDuration = [...completedCalls].sort((a, b) => (a.duration || 0) - (b.duration || 0));
    
    return {
      totalCalls: completedCalls.length,
      successCalls: successCalls.length,
      errorCalls: errorCalls.length,
      avgResponseTime: Math.round(avgResponseTime),
      slowestEndpoint: sortedByDuration[sortedByDuration.length - 1]?.endpoint || '-',
      fastestEndpoint: sortedByDuration[0]?.endpoint || '-',
      errorRate: Math.round((errorCalls.length / completedCalls.length) * 100),
    };
  }

  /**
   * 获取最近的错误
   */
  getRecentErrors(limit = 10): APICall[] {
    return this.calls
      .filter(c => c.status && c.status >= 400)
      .slice(-limit)
      .reverse();
  }

  /**
   * 获取慢请求
   */
  getSlowCalls(threshold = 1000): APICall[] {
    return this.calls
      .filter(c => c.duration && c.duration > threshold)
      .reverse();
  }

  /**
   * 打印统计信息到控制台
   */
  printStats(): void {
    const metrics = this.getMetrics();
    
    console.group('📊 API 监控统计');
    console.log(`总调用次数: ${metrics.totalCalls}`);
    console.log(`成功: ${metrics.successCalls} | 失败: ${metrics.errorCalls}`);
    console.log(`平均响应时间: ${metrics.avgResponseTime}ms`);
    console.log(`错误率: ${metrics.errorRate}%`);
    console.log(`最慢端点: ${metrics.slowestEndpoint}`);
    console.log(`最快端点: ${metrics.fastestEndpoint}`);
    
    const recentErrors = this.getRecentErrors(5);
    if (recentErrors.length > 0) {
      console.group('最近错误:');
      recentErrors.forEach(call => {
        console.log(`${call.method} ${call.endpoint} - ${call.status} (${call.duration}ms)`);
        if (call.error) console.log('  Error:', call.error);
      });
      console.groupEnd();
    }
    
    const slowCalls = this.getSlowCalls();
    if (slowCalls.length > 0) {
      console.group('慢请求 (>1000ms):');
      slowCalls.forEach(call => {
        console.log(`${call.method} ${call.endpoint} - ${call.duration}ms`);
      });
      console.groupEnd();
    }
    
    console.groupEnd();
  }

  /**
   * 清空历史记录
   */
  clear(): void {
    this.calls = [];
  }
}

// 创建全局实例
export const apiMonitor = new APIMonitor();

/**
 * 包装 fetch 函数以监控 API 调用
 */
export function monitoredFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const url = typeof input === 'string' ? input : input.toString();
  const method = init?.method || 'GET';
  
  // 提取端点路径
  const endpoint = url.replace(/^.*\/api/, '/api');
  
  const callIndex = apiMonitor.startCall(endpoint, method);
  
  return fetch(input, init)
    .then(response => {
      apiMonitor.endCall(callIndex, response.status);
      return response;
    })
    .catch(error => {
      apiMonitor.endCall(callIndex, 0, error.message);
      throw error;
    });
}

// 导出到全局
declare global {
  interface Window {
    apiMonitor: APIMonitor;
  }
}

if (typeof window !== 'undefined') {
  window.apiMonitor = apiMonitor;
}

export default apiMonitor;
