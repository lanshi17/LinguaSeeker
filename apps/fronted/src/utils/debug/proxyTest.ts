/**
 * 代理连接测试工具
 */

interface TestResult {
  name: string;
  success: boolean;
  status?: number;
  statusText?: string;
  data?: unknown;
  error?: string;
  duration: number;
}

/**
 * 测试单个端点
 */
async function testEndpoint(
  name: string,
  url: string,
  method: string = 'GET',
  body?: BodyInit
): Promise<TestResult> {
  const start = performance.now();
  try {
    const response = await fetch(url, {
      method,
      body,
      cache: 'no-cache',
    });
    const duration = Math.round(performance.now() - start);
    
    let data: unknown;
    try {
      data = await response.clone().json();
    } catch {
      data = await response.clone().text();
    }
    
    return {
      name,
      success: response.ok,
      status: response.status,
      statusText: response.statusText,
      data,
      duration,
    };
  } catch (error) {
    return {
      name,
      success: false,
      error: error instanceof Error ? error.message : String(error),
      duration: Math.round(performance.now() - start),
    };
  }
}

/**
 * 运行完整的代理测试
 */
export async function runProxyTest(): Promise<TestResult[]> {
  const results: TestResult[] = [];
  
  console.group('🧪 代理连接测试');
  
  // 测试 1: 直接访问后端根路径
  results.push(await testEndpoint(
    '直接访问后端 (/)',
    'http://localhost:8000/'
  ));
  
  // 测试 2: 通过代理访问根路径
  results.push(await testEndpoint(
    '代理访问后端 (/api/)',
    '/api/'
  ));
  
  // 测试 3: 通过代理访问 API
  results.push(await testEndpoint(
    '代理访问 API (/api/v1)',
    '/api/v1'
  ));
  
  // 测试 4: 测试 PDF 上传端点 (OPTIONS)
  results.push(await testEndpoint(
    'PDF 上传端点 (OPTIONS)',
    '/api/v1/pdf/upload',
    'OPTIONS'
  ));
  
  // 测试 5: 测试 PDF 上传 (POST)
  const formData = new FormData();
  formData.append('test', 'data');
  results.push(await testEndpoint(
    'PDF 上传测试 (POST)',
    '/api/v1/pdf/upload',
    'POST',
    formData
  ));
  
  // 打印结果
  results.forEach(result => {
    const icon = result.success ? '✅' : '❌';
    const status = result.status ? `(${result.status})` : '';
    console.log(`${icon} ${result.name} ${status} - ${result.duration}ms`);
    
    if (!result.success) {
      if (result.error) {
        console.log('   错误:', result.error);
      } else if (result.data) {
        console.log('   响应:', result.data);
      }
    }
  });
  
  // 分析结果
  const directTest = results.find(r => r.name.includes('直接访问'));
  const proxyTest = results.find(r => r.name.includes('代理访问后端'));
  
  console.log('');
  console.log('【诊断结果】');
  
  if (!directTest?.success && directTest?.status === 0) {
    console.log('❌ 后端服务未启动');
    console.log('   请运行: uvicorn main:app --reload --port 8000');
  } else if (directTest?.success && !proxyTest?.success) {
    console.log('❌ 代理配置有问题');
    console.log('   建议:');
    console.log('   1. 重启前端服务: npm run dev');
    console.log('   2. 强制刷新浏览器: Ctrl+Shift+R');
    console.log('   3. 检查 vite.config.ts 配置');
  } else if (proxyTest?.success) {
    console.log('✅ 代理连接正常');
    console.log('   前端可以通过代理访问后端');
  }
  
  console.groupEnd();
  return results;
}

/**
 * 快速检查代理是否工作
 */
export async function quickProxyCheck(): Promise<{
  working: boolean;
  backendRunning: boolean;
  message: string;
}> {
  try {
    // 直接访问后端
    const direct = await fetch('http://localhost:8000/', {
      method: 'GET',
      signal: AbortSignal.timeout(2000),
    }).catch(() => null);
    
    // 通过代理访问
    const proxy = await fetch('/api/', {
      method: 'GET',
      signal: AbortSignal.timeout(2000),
    }).catch(() => null);
    
    const backendRunning = !!direct;
    const proxyWorking = !!proxy;
    
    if (!backendRunning) {
      return {
        working: false,
        backendRunning: false,
        message: '后端服务未启动 (localhost:8000)',
      };
    }
    
    if (!proxyWorking) {
      return {
        working: false,
        backendRunning: true,
        message: '代理不工作，请重启前端服务',
      };
    }
    
    return {
      working: true,
      backendRunning: true,
      message: '代理连接正常',
    };
  } catch {
    return {
      working: false,
      backendRunning: false,
      message: '检查失败',
    };
  }
}

// 导出到全局
declare global {
  interface Window {
    proxyTest: {
      runProxyTest: typeof runProxyTest;
      quickProxyCheck: typeof quickProxyCheck;
    };
  }
}

if (typeof window !== 'undefined') {
  window.proxyTest = {
    runProxyTest,
    quickProxyCheck,
  };
}
