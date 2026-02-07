/**
 * 后端状态指示器
 * 显示后端连接和数据库状态
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Database, Server, AlertCircle, CheckCircle, Loader2, RefreshCw } from 'lucide-react';
import './BackendStatus.css';

type StatusType = 'checking' | 'connected' | 'error' | 'degraded';

interface BackendStatusData {
  api: boolean;
  database: boolean;
  ws: boolean;
  latency: number;
}

export const BackendStatus: React.FC = () => {
  const [status, setStatus] = useState<StatusType>('checking');
  const [details, setDetails] = useState<BackendStatusData | null>(null);
  const [message, setMessage] = useState('检查中...');

  const checkStatus = useCallback(async () => {
    setStatus('checking');
    setMessage('检查后端状态...');

    const start = performance.now();
    
    try {
      // 检查 API 健康
      const healthRes = await fetch('/api/v1/health', {
        method: 'GET',
        cache: 'no-cache',
      });
      
      const latency = Math.round(performance.now() - start);
      
      // 检查数据库状态（通过尝试访问任务端点）
      let dbStatus = false;
      try {
        const dbRes = await fetch('/api/v1/tasks/test-connection', {
          method: 'GET',
          cache: 'no-cache',
        });
        // 404 表示数据库连接正常（端点存在但任务不存在）
        // 500 表示数据库问题
        dbStatus = dbRes.status === 404 || dbRes.status === 200;
      } catch {
        dbStatus = false;
      }
      
      // 检查 WebSocket（假设 ws 也使用 8000 端口）
      const wsStatus = healthRes.ok; // 简化：假设 HTTP 正常则 WS 也正常
      
      const statusData: BackendStatusData = {
        api: healthRes.ok,
        database: dbStatus,
        ws: wsStatus,
        latency,
      };
      
      setDetails(statusData);
      
      // 确定整体状态
      if (healthRes.ok && dbStatus) {
        setStatus('connected');
        setMessage(`后端运行正常 (${latency}ms)`);
      } else if (healthRes.ok && !dbStatus) {
        setStatus('degraded');
        setMessage('API 正常但数据库可能有问题');
      } else {
        setStatus('error');
        setMessage('后端服务不可用');
      }
    } catch {
      setStatus('error');
      setMessage('无法连接到后端');
      setDetails({
        api: false,
        database: false,
        ws: false,
        latency: 0,
      });
    }
  }, []);

  useEffect(() => {
    checkStatus();
    // 每 30 秒检查一次
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, [checkStatus]);

  const getIcon = () => {
    switch (status) {
      case 'connected':
        return <CheckCircle size={16} className="status-icon connected" />;
      case 'error':
        return <AlertCircle size={16} className="status-icon error" />;
      case 'degraded':
        return <AlertCircle size={16} className="status-icon warning" />;
      case 'checking':
        return <Loader2 size={16} className="status-icon checking spin" />;
    }
  };

  return (
    <div className={`backend-status ${status}`}>
      <div className="status-main" onClick={checkStatus}>
        {getIcon()}
        <span className="status-text">{message}</span>
        <RefreshCw size={12} className="refresh-icon" />
      </div>
      
      {details && status !== 'checking' && (
        <div className="status-details">
          <div className="detail-item">
            <Server size={12} />
            <span>API</span>
            <span className={details.api ? 'ok' : 'error'}>
              {details.api ? '正常' : '异常'}
            </span>
          </div>
          <div className="detail-item">
            <Database size={12} />
            <span>数据库</span>
            <span className={details.database ? 'ok' : 'error'}>
              {details.database ? '正常' : '异常'}
            </span>
          </div>
          <div className="detail-item">
            <span>延迟</span>
            <span className="latency">{details.latency}ms</span>
          </div>
        </div>
      )}
      
      {status === 'error' && (
        <div className="status-help">
          <p>请确保后端服务已启动：</p>
          <code>uvicorn main:app --reload --port 8000</code>
        </div>
      )}
      
      {status === 'degraded' && (
        <div className="status-help">
          <p>数据库连接可能有问题，部分功能受限</p>
        </div>
      )}
    </div>
  );
};

export default BackendStatus;
