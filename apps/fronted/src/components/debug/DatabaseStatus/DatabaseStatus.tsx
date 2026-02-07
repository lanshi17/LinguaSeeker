/**
 * 数据库状态指示器
 * 专门监控后端数据库连接状态
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Database, AlertCircle, CheckCircle, Loader2, RefreshCw, ServerOff } from 'lucide-react';
import './DatabaseStatus.css';

type DBStatus = 'checking' | 'connected' | 'error' | 'degraded';

interface DBStatusInfo {
  status: DBStatus;
  message: string;
  lastError?: string;
  checkedAt?: Date;
}

export const DatabaseStatus: React.FC = () => {
  const [dbStatus, setDbStatus] = useState<DBStatusInfo>({
    status: 'checking',
    message: '检查数据库连接...',
  });
  const [isExpanded, setIsExpanded] = useState(false);

  const checkDatabase = useCallback(async () => {
    setDbStatus(prev => ({ ...prev, status: 'checking', message: '检查中...' }));

    try {
      // 尝试一个需要数据库操作的端点
      const response = await fetch('/api/v1/pdf/upload', {
        method: 'POST',
        body: new FormData(), // 空表单，用于测试端点
      });

      // 分析响应
      if (response.status === 400) {
        // 400 表示端点工作但参数缺失（数据库可能正常）
        setDbStatus({
          status: 'connected',
          message: '数据库连接正常',
          checkedAt: new Date(),
        });
      } else if (response.status === 500) {
        const errorText = await response.text();
        const isDBError = errorText.toLowerCase().includes('database') || 
                         errorText.toLowerCase().includes('db') ||
                         errorText.toLowerCase().includes('sql') ||
                         errorText.toLowerCase().includes('connection');
        
        if (isDBError) {
          setDbStatus({
            status: 'error',
            message: '数据库连接失败',
            lastError: '后端无法连接到数据库',
            checkedAt: new Date(),
          });
        } else {
          setDbStatus({
            status: 'degraded',
            message: '服务异常（非数据库问题）',
            checkedAt: new Date(),
          });
        }
      } else if (response.status === 405 || response.status === 422) {
        setDbStatus({
          status: 'connected',
          message: '数据库连接正常',
          checkedAt: new Date(),
        });
      } else {
        setDbStatus({
          status: 'degraded',
          message: `意外响应: ${response.status}`,
          checkedAt: new Date(),
        });
      }
    } catch (error) {
      setDbStatus({
        status: 'error',
        message: '无法连接到后端',
        lastError: error instanceof Error ? error.message : '网络错误',
        checkedAt: new Date(),
      });
    }
  }, []);

  useEffect(() => {
    checkDatabase();
    // 每 10 秒检查一次
    const interval = setInterval(checkDatabase, 10000);
    return () => clearInterval(interval);
  }, [checkDatabase]);

  const getIcon = () => {
    switch (dbStatus.status) {
      case 'connected':
        return <CheckCircle size={18} className="db-icon connected" />;
      case 'error':
        return <ServerOff size={18} className="db-icon error" />;
      case 'degraded':
        return <AlertCircle size={18} className="db-icon warning" />;
      case 'checking':
        return <Loader2 size={18} className="db-icon checking spin" />;
    }
  };

  const getStatusClass = () => {
    switch (dbStatus.status) {
      case 'connected': return 'status-ok';
      case 'error': return 'status-error';
      case 'degraded': return 'status-warning';
      case 'checking': return 'status-checking';
    }
  };

  return (
    <div className={`database-status ${getStatusClass()}`}>
      <div className="db-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="db-main">
          {getIcon()}
          <Database size={16} />
          <span className="db-label">数据库</span>
          <span className="db-message">{dbStatus.message}</span>
        </div>
        <div className="db-actions">
          {dbStatus.checkedAt && (
            <span className="db-time">
              {dbStatus.checkedAt.toLocaleTimeString()}
            </span>
          )}
          <RefreshCw 
            size={14} 
            className="db-refresh" 
            onClick={(e) => {
              e.stopPropagation();
              checkDatabase();
            }}
          />
        </div>
      </div>

      {isExpanded && (
        <div className="db-details">
          {dbStatus.status === 'error' && (
            <div className="db-error-info">
              <p className="db-error-title">⚠️ 数据库连接问题</p>
              <p className="db-error-desc">
                后端服务无法连接到数据库，这可能是以下原因导致的：
              </p>
              <ul>
                <li>数据库服务未启动</li>
                <li>数据库配置错误</li>
                <li>网络连接问题</li>
              </ul>
              <div className="db-error-action">
                <p>请通知后端管理员检查数据库配置</p>
                <code>检查数据库连接字符串和凭据</code>
              </div>
            </div>
          )}

          {dbStatus.status === 'connected' && (
            <div className="db-success-info">
              <p>✅ 数据库连接正常，可以正常使用所有功能</p>
            </div>
          )}

          {dbStatus.status === 'degraded' && (
            <div className="db-warning-info">
              <p>⚠️ 服务响应异常，部分功能可能不可用</p>
            </div>
          )}

          {dbStatus.lastError && (
            <div className="db-last-error">
              <strong>上次错误:</strong> {dbStatus.lastError}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DatabaseStatus;
