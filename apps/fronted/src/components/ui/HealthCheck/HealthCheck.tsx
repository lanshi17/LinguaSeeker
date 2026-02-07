/**
 * API 健康检查组件
 * 显示所有业务端点的状态
 */
import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Activity, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import './HealthCheck.css';

interface EndpointStatus {
  name: string;
  path: string;
  method: string;
  status: 'checking' | 'ok' | 'error' | 'warning';
  httpStatus?: number;
  duration?: number;
  error?: string;
}

const ENDPOINTS_TO_CHECK = [
  { name: '健康检查', path: '/api/v1/health', method: 'GET', expect: [200] },
  { name: 'PDF 上传 (表单)', path: '/api/v1/pdf/upload', method: 'OPTIONS', expect: [200, 405] },
  { name: 'PMID 获取', path: '/api/v1/pdf/fetch-by-pmid?pmid=123', method: 'OPTIONS', expect: [200, 405] },
  { name: 'DOI 获取', path: '/api/v1/pdf/fetch-by-doi?doi=10.1000/test', method: 'OPTIONS', expect: [200, 405] },
  { name: '任务状态', path: '/api/v1/tasks/test-id', method: 'GET', expect: [200, 404] },
  { name: '任务进度', path: '/api/v1/tasks/test-id/progress', method: 'GET', expect: [200, 404] },
];

export const HealthCheck: React.FC = () => {
  const [endpoints, setEndpoints] = useState<EndpointStatus[]>([]);
  const [isChecking, setIsChecking] = useState(false);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const checkAll = useCallback(async () => {
    setIsChecking(true);
    setEndpoints(ENDPOINTS_TO_CHECK.map(e => ({ ...e, status: 'checking' })));

    const results: EndpointStatus[] = [];

    for (const endpoint of ENDPOINTS_TO_CHECK) {
      const start = performance.now();
      try {
        const response = await fetch(endpoint.path, {
          method: endpoint.method,
          cache: 'no-cache',
        });
        
        const duration = Math.round(performance.now() - start);
        const isOk = endpoint.expect.includes(response.status);
        
        results.push({
          ...endpoint,
          status: isOk ? 'ok' : 'warning',
          httpStatus: response.status,
          duration,
        });
      } catch (error) {
        results.push({
          ...endpoint,
          status: 'error',
          error: error instanceof Error ? error.message : '连接失败',
        });
      }
    }

    setEndpoints(results);
    setLastCheck(new Date());
    setIsChecking(false);
  }, []);

  useEffect(() => {
    checkAll();
  }, [checkAll]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ok': return <CheckCircle size={16} className="status-ok" />;
      case 'warning': return <AlertTriangle size={16} className="status-warning" />;
      case 'error': return <XCircle size={16} className="status-error" />;
      case 'checking': return <RefreshCw size={16} className="spin" />;
      default: return null;
    }
  };

  const getStatusText = (ep: EndpointStatus) => {
    if (ep.status === 'checking') return '检查中...';
    if (ep.status === 'error') return ep.error || '连接失败';
    if (ep.httpStatus) return `HTTP ${ep.httpStatus}${ep.duration ? ` (${ep.duration}ms)` : ''}`;
    return '';
  };

  const okCount = endpoints.filter(e => e.status === 'ok').length;
  const hasErrors = endpoints.some(e => e.status === 'error');

  return (
    <div className="health-check">
      <div className="health-header">
        <h3>
          <Activity size={18} />
          API 端点健康检查
        </h3>
        <div className="health-summary">
          {endpoints.length > 0 && (
            <span className={hasErrors ? 'has-errors' : 'all-ok'}>
              {okCount}/{endpoints.length} 正常
            </span>
          )}
          <button 
            onClick={checkAll} 
            disabled={isChecking}
            className="btn-refresh"
          >
            <RefreshCw size={14} className={isChecking ? 'spin' : ''} />
            {isChecking ? '检查中...' : '重新检查'}
          </button>
        </div>
      </div>

      <div className="endpoints-list">
        {endpoints.map((ep, idx) => (
          <div key={idx} className={`endpoint-item ${ep.status}`}>
            <div className="endpoint-info">
              {getStatusIcon(ep.status)}
              <span className="endpoint-name">{ep.name}</span>
              <code className="endpoint-path">{ep.path}</code>
            </div>
            <span className="endpoint-status">{getStatusText(ep)}</span>
          </div>
        ))}
      </div>

      {lastCheck && (
        <div className="last-check">
          上次检查: {lastCheck.toLocaleTimeString()}
        </div>
      )}

      <div className="health-notes">
        <h4>说明</h4>
        <ul>
          <li>✅ <strong>正常</strong>: 端点可访问，返回预期状态码</li>
          <li>⚠️ <strong>警告</strong>: 端点可访问，但返回非预期状态码</li>
          <li>❌ <strong>错误</strong>: 无法连接到端点</li>
          <li>对于任务相关端点，404 表示端点存在但任务不存在（正常）</li>
        </ul>
      </div>
    </div>
  );
};

export default HealthCheck;
