import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { API_BASE_URL } from './services/api';
import { checkBackendRunning } from './utils/api/apiDebug';
import { fullNetworkDiagnostic } from './utils/debug/networkTest';
import { printApiEndpoints } from './utils/api/apiEndpoints';
import './utils/debug/proxyTest';
import './utils/debug/healthCheck';
import './utils/api/apiMonitor';
import './index.css';

// 打印 API 配置信息（开发调试用）
console.log('%c🔧 Multi-ACMG 前端启动', 'font-size: 16px; font-weight: bold; color: #3b82f6;');
console.log('[配置] 运行模式:', import.meta.env.MODE);
console.log('[配置] API 基础地址:', API_BASE_URL);
console.log('[配置] 预期后端:', 'http://localhost:8000');
console.log('');

// 打印 API 端点清单
printApiEndpoints();

console.log('');
console.log('%c【快速修复】', 'font-weight: bold; color: #f59e0b;');
console.log('1. 确保后端已启动: uvicorn main:app --reload --port 8000');
console.log('2. 重启前端服务: npm run dev');
console.log('3. 强制刷新: Ctrl+Shift+R');
console.log('');
console.log('%c【诊断命令】', 'font-weight: bold; color: #10b981;');
console.log('• 运行网络诊断: networkTest.fullNetworkDiagnostic()');
console.log('• 检查后端状态: npm run check-backend');
console.log('• 查看 API 状态: 点击左侧导航栏底部指示器');
console.log('');

// 自动检查后端连接
if (import.meta.env.DEV) {
  console.log('[检查] 正在检测后端服务...');
  checkBackendRunning().then(result => {
    if (result.ok) {
      console.log('%c✅ 后端服务已连接', 'color: #10b981; font-weight: bold;');
    } else {
      console.warn('%c❌ 后端服务未运行', 'color: #ef4444; font-weight: bold;');
      console.log('[提示] 请启动后端服务: uvicorn main:app --reload --port 8000');
    }
  });
  
  // 3 秒后自动运行网络诊断
  setTimeout(() => {
    console.log('');
    console.log('[自动诊断] 正在运行网络测试...');
    fullNetworkDiagnostic();
  }, 3000);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
