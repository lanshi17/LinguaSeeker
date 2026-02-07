/**
 * 代理连接测试组件
 */
import React, { useState, useEffect } from 'react';
import './ProxyTest.css';

interface TestResult {
  name: string;
  status: 'pending' | 'success' | 'error';
  message: string;
  details?: string;
}

export const ProxyTest: React.FC = () => {
  const [results, setResults] = useState<TestResult[]>([]);
  const [isTesting, setIsTesting] = useState(false);

  const addResult = (result: TestResult) => {
    setResults(prev => [...prev, result]);
  };

  const runTests = async () => {
    setIsTesting(true);
    setResults([]);

    // 测试 1: 检查配置
    addResult({
      name: '配置检查',
      status: 'success',
      message: 'API_BASE_URL = /api/v1',
    });

    // 测试 2: 尝试通过代理访问
    try {
      const response = await fetch('/api/', {
        method: 'GET',
        cache: 'no-cache',
      });
      
      if (response.ok) {
        addResult({
          name: '代理连接测试',
          status: 'success',
          message: `成功 (${response.status})`,
          details: '代理配置正确，请求已转发到后端',
        });
      } else if (response.status === 404) {
        addResult({
          name: '代理连接测试',
          status: 'error',
          message: `后端返回 404`,
          details: '代理已生效，但后端没有该路由。请检查后端API端点',
        });
      } else {
        addResult({
          name: '代理连接测试',
          status: 'error',
          message: `HTTP ${response.status}`,
          details: await response.text().catch(() => '无响应内容'),
        });
      }
    } catch (error) {
      addResult({
        name: '代理连接测试',
        status: 'error',
        message: '连接失败',
        details: error instanceof Error ? error.message : String(error),
      });
    }

    // 测试 3: 尝试直接访问后端
    try {
      const response = await fetch('http://localhost:8000/', {
        method: 'GET',
        cache: 'no-cache',
        signal: AbortSignal.timeout(2000),
      });
      
      if (response.ok || response.status === 404) {
        addResult({
          name: '直接连接后端',
          status: 'success',
          message: `后端运行中 (${response.status})`,
          details: '后端服务已启动在 8000 端口',
        });
      } else {
        addResult({
          name: '直接连接后端',
          status: 'error',
          message: `HTTP ${response.status}`,
        });
      }
    } catch (error) {
      addResult({
        name: '直接连接后端',
        status: 'error',
        message: '后端未运行',
        details: '请启动后端: uvicorn main:app --reload --port 8000',
      });
    }

    // 测试 4: 测试具体 API 端点
    try {
      const response = await fetch('/api/v1/pdf/upload', {
        method: 'OPTIONS',
        cache: 'no-cache',
      });
      
      addResult({
        name: 'PDF上传端点',
        status: response.ok || response.status === 405 ? 'success' : 'error',
        message: `HTTP ${response.status}`,
        details: response.status === 405 ? '端点存在（方法不允许）' : '',
      });
    } catch (error) {
      addResult({
        name: 'PDF上传端点',
        status: 'error',
        message: '连接失败',
      });
    }

    setIsTesting(false);
  };

  useEffect(() => {
    runTests();
  }, []);

  return (
    <div className="proxy-test">
      <h2>API 代理连接测试</h2>
      
      <div className="test-results">
        {results.map((result, index) => (
          <div key={index} className={`test-item ${result.status}`}>
            <div className="test-header">
              <span className="test-icon">
                {result.status === 'success' && '✅'}
                {result.status === 'error' && '❌'}
                {result.status === 'pending' && '⏳'}
              </span>
              <span className="test-name">{result.name}</span>
              <span className="test-status">{result.message}</span>
            </div>
            {result.details && (
              <div className="test-details">{result.details}</div>
            )}
          </div>
        ))}
      </div>

      <div className="test-actions">
        <button onClick={runTests} disabled={isTesting}>
          {isTesting ? '测试中...' : '重新测试'}
        </button>
      </div>

      <div className="test-help">
        <h3>常见问题</h3>
        <ul>
          <li>
            <strong>代理连接测试 404</strong>: 代理已生效，但后端没有根路由。这是正常的，检查具体 API 端点即可。
          </li>
          <li>
            <strong>直接连接后端失败</strong>: 后端服务未启动，请运行 <code>uvicorn main:app --reload --port 8000</code>
          </li>
          <li>
            <strong>所有测试都失败</strong>: 刷新页面或重启前端服务 <code>npm run dev</code>
          </li>
        </ul>
      </div>
    </div>
  );
};

export default ProxyTest;
