/**
 * 网络连接测试工具
 * 用于测试前后端连接
 */

const API_BASE = '/api/v1';

interface TestResult {
  name: string;
  success: boolean;
  status?: number;
  statusText?: string;
  response?: unknown;
  error?: string;
  duration: number;
}

/**
 * 执行单个测试
 */
async function runTest(
  name: string,
  testFn: () => Promise<Response>
): Promise<TestResult> {
  const start = performance.now();
  try {
    const response = await testFn();
    const duration = Math.round(performance.now() - start);
    
    // 尝试解析响应
    let responseData: unknown;
    try {
      responseData = await response.clone().json();
    } catch {
      responseData = await response.clone().text();
    }
    
    return {
      name,
      success: response.ok,
      status: response.status,
      statusText: response.statusText,
      response: responseData,
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
 * 运行所有连接测试
 */
export async function runNetworkTests(): Promise<TestResult[]> {
  const results: TestResult[] = [];
  
  // 测试 1: 直接检查后端根路径
  results.push(await runTest('后端根路径', () => 
    fetch('http://localhost:8000/', { method: 'GET' })
  ));
  
  // 测试 2: 检查 API 路径（通过代理）
  results.push(await runTest('API 代理路径', () => 
    fetch(`${API_BASE}/health`, { method: 'GET' })
  ));
  
  // 测试 3: 测试 PDF 上传端点（OPTIONS 预检）
  results.push(await runTest('PDF 上传端点', () => 
    fetch(`${API_BASE}/pdf/upload`, { 
      method: 'OPTIONS',
      headers: { 'Access-Control-Request-Method': 'POST' }
    })
  ));
  
  // 测试 4: 测试 PMID 获取端点（OPTIONS 预检）
  results.push(await runTest('PMID 获取端点', () => 
    fetch(`${API_BASE}/pdf/fetch-by-pmid?pmid=123`, { 
      method: 'OPTIONS',
      headers: { 'Access-Control-Request-Method': 'POST' }
    })
  ));
  
  // 测试 5: 实际的 POST 请求（不带 body 测试连通性）
  results.push(await runTest('PDF 上传 POST', () => 
    fetch(`${API_BASE}/pdf/upload`, { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test: true })
    })
  ));
  
  return results;
}

/**
 * 打印测试结果
 */
export function printTestResults(results: TestResult[]): void {
  console.group('🧪 网络连接测试结果');
  console.log('');
  
  const successCount = results.filter(r => r.success).length;
  const failCount = results.length - successCount;
  
  console.log(`通过: ${successCount}/${results.length}, 失败: ${failCount}/${results.length}`);
  console.log('');
  
  results.forEach(result => {
    const icon = result.success ? '✅' : '❌';
    const statusStr = result.status ? `(${result.status})` : '';
    console.log(`${icon} ${result.name} ${statusStr} - ${result.duration}ms`);
    
    if (!result.success) {
      if (result.error) {
        console.log(`   错误: ${result.error}`);
      } else if (result.response) {
        console.log(`   响应:`, result.response);
      }
    }
  });
  
  console.log('');
  
  // 分析结果
  const proxyTest = results.find(r => r.name === 'API 代理路径');
  const backendTest = results.find(r => r.name === '后端根路径');
  
  if (backendTest?.success && !proxyTest?.success) {
    console.log('💡 分析: 后端运行正常，但代理转发失败');
    console.log('   建议: 检查 vite.config.ts 代理配置，重启前端服务');
  } else if (!backendTest?.success) {
    console.log('💡 分析: 后端服务未运行');
    console.log('   建议: 启动后端服务 uvicorn main:app --reload --port 8000');
  } else if (proxyTest?.success) {
    console.log('💡 分析: 代理连接正常，但 API 端点可能有问题');
    console.log('   建议: 检查后端 API 路由配置');
  }
  
  console.groupEnd();
}

/**
 * 检查代理是否生效
 */
export async function checkProxyWorking(): Promise<boolean> {
  try {
    // 直接访问后端
    const directResponse = await fetch('http://localhost:8000/', {
      method: 'GET',
      signal: AbortSignal.timeout(2000),
    });
    
    // 通过代理访问
    const proxyResponse = await fetch('/api/health', {
      method: 'GET',
      signal: AbortSignal.timeout(2000),
    });
    
    // 如果直接访问成功但代理失败，说明代理有问题
    if (directResponse.ok && !proxyResponse.ok && proxyResponse.status !== 404) {
      return false;
    }
    
    return true;
  } catch {
    return false;
  }
}

/**
 * 获取调试信息
 */
export function getDebugInfo(): Record<string, string> {
  return {
    'User Agent': navigator.userAgent,
    '当前 URL': window.location.href,
    'API 基础路径': API_BASE,
    '运行模式': import.meta.env.MODE,
    'Vite 基础 URL': import.meta.env.BASE_URL || '/',
    '最后刷新': new Date().toLocaleString(),
  };
}

/**
 * 完整的网络诊断
 */
export async function fullNetworkDiagnostic(): Promise<void> {
  console.clear();
  console.log('%c🔧 Multi-ACMG 网络诊断', 'font-size: 18px; font-weight: bold; color: #3b82f6;');
  console.log('=' .repeat(60));
  console.log('');
  
  // 1. 打印调试信息
  console.log('【环境信息】');
  const debugInfo = getDebugInfo();
  Object.entries(debugInfo).forEach(([key, value]) => {
    console.log(`  ${key}: ${value}`);
  });
  console.log('');
  
  // 2. 运行网络测试
  console.log('【运行测试】');
  const results = await runNetworkTests();
  printTestResults(results);
  
  // 3. 检查代理
  console.log('');
  console.log('【代理检查】');
  const proxyWorking = await checkProxyWorking();
  if (proxyWorking) {
    console.log('  ✅ 代理配置正常');
  } else {
    console.log('  ❌ 代理可能有问题');
    console.log('  💡 尝试以下修复：');
    console.log('     1. 重启前端服务: npm run dev');
    console.log('     2. 强制刷新页面: Ctrl+Shift+R');
    console.log('     3. 清除浏览器缓存');
  }
  
  console.log('');
  console.log('=' .repeat(60));
}

// 导出到全局以便控制台调用
if (typeof window !== 'undefined') {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as unknown as Record<string, unknown>).networkTest = {
    runNetworkTests,
    printTestResults,
    fullNetworkDiagnostic,
    getDebugInfo,
  };
}
