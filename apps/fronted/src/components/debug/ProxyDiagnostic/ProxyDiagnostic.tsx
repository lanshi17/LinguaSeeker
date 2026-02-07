/**
 * 代理诊断组件
 * 用于可视化显示代理连接状态
 */
import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Server, AlertCircle, CheckCircle } from 'lucide-react';
import './ProxyDiagnostic.css';

interface TestResult {
  name: string;
  success: boolean;
  status?: number;
  error?: string;
  duration: number;
}

export const ProxyDiagnostic: React.FC = () => {
  const [results, setResults] = useState<TestResult[]>([]);
  const [isTesting, setIsTesting] = useState(false);
  const [overallStatus, setOverallStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const runTest = useCallback(async () => {
    setIsTesting(true);
    setResults([]);
    setOverallStatus('idle');

    const tests = [
      { name: '直接访问后端 (/)', url: 'http://localhost:8000/' },
      { name: '代理访问 (/api/)', url: '/api/' },
      { name: '代理访问 API (/api/v1)', url: '/api/v1' },
      { name: 'PDF 上传端点', url: '/api/v1/pdf/upload', method: 'OPTIONS' },
    ];

    const newResults: TestResult[] = [];

    for (const test of tests) {
      const start = performance.now();
      try {
        const response = await fetch(test.url, {
          method: test.method || 'GET',
          cache: 'no-cache',
        });
        
        newResults.push({
          name: test.name,
          success: response.ok || response.status === 404, // 404 表示连接成功但端点不存在
          status: response.status,
          duration: Math.round(performance.now() - start),
        });
      } catch (error) {
        newResults.push({
          name: test.name,
          success: false,
          error: error instanceof Error ? error.message : '连接失败',
          duration: Math.round(performance.now() - start),
        });
      }
    }

    setResults(newResults);
    
    // 判断整体状态
    const proxyTest = newResults.find(r => r.name.includes('代理访问'));
    if (proxyTest?.success) {
      setOverallStatus('success');
    } else {
      setOverallStatus('error');
    }
    
    setIsTesting(false);
  }, []);

  useEffect(() => {
    runTest();
  }, [runTest]);

  const getRecommendation = () => {
    const directTest = results.find(r => r.name.includes('直接访问'));
    const proxyTest = results.find(r => r.name.includes('代理访问'));

    if (!directTest?.success) {
      return {
        title: '后端服务未启动',
        steps: [
          '进入后端项目目录',
          '运行: uvicorn main:app --reload --port 8000',
          '确保看到 "Uvicorn running on http://0.0.0.0:8000"',
        ],
      };
    }

    if (!proxyTest?.success) {
      return {
        title: '代理配置需要重启',
        steps: [
          '停止当前前端服务 (Ctrl+C)',
          '清除缓存: rm -rf node_modules/.vite',
          '重启服务: npm run dev',
          '强制刷新浏览器: Ctrl+Shift+R',
        ],
      };
    }

    return null;
  };

  const recommendation = getRecommendation();

  return (
    <div className="proxy-diagnostic">
      <div className="diagnostic-header">
        <h3>
          <Server size={18} />
          代理连接诊断
        </h3>
        <div className={`status-badge ${overallStatus}`}>
          {overallStatus === 'success' && <><CheckCircle size={14} /> 正常</>}
          {overallStatus === 'error' && <><AlertCircle size={14} /> 异常</>}
          {overallStatus === 'idle' && <><RefreshCw size={14} className="spin" /> 检测中</>}
        </div>
      </div>

      <div className="test-results">
        {results.map((result, idx) => (
          <div key={idx} className={`test-item ${result.success ? 'success' : 'error'}`}>
            <span className="test-icon">
              {result.success ? '✅' : '❌'}
            </span>
            <span className="test-name">{result.name}</span>
            <span className="test-status">
              {result.status ? `HTTP ${result.status}` : result.error}
            </span>
            <span className="test-duration">{result.duration}ms</span>
          </div>
        ))}
        {isTesting && results.length === 0 && (
          <div className="test-item pending">
            <span className="test-icon"><RefreshCw size={14} className="spin" /></span>
            <span className="test-name">正在测试连接...</span>
          </div>
        )}
      </div>

      {recommendation && (
        <div className="recommendation">
          <h4>{recommendation.title}</h4>
          <ol>
            {recommendation.steps.map((step, idx) => (
              <li key={idx}>{step}</li>
            ))}
          </ol>
        </div>
      )}

      <div className="diagnostic-actions">
        <button onClick={runTest} disabled={isTesting}>
          <RefreshCw size={14} className={isTesting ? 'spin' : ''} />
          {isTesting ? '测试中...' : '重新测试'}
        </button>
      </div>

      <div className="console-hint">
        <p>💡 在浏览器控制台运行 <code>proxyTest.runProxyTest()</code> 获取详细日志</p>
      </div>
    </div>
  );
};

export default ProxyDiagnostic;
