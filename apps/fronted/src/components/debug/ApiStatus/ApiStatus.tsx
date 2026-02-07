/**
 * API 连接状态组件
 * 用于显示后端连接状态和诊断信息
 */
import React, { useState, useEffect, useCallback } from 'react';
import { AlertCircle, CheckCircle, Loader2, Server, RefreshCw, Terminal } from 'lucide-react';
import { quickCheck, runFullDiagnostics, getApiConfig } from '../../../utils/api/apiDebug';
import './ApiStatus.css';

interface ApiStatusProps {
  /** 是否自动检查 */
  autoCheck?: boolean;
  /** 自动检查间隔 (ms) */
  checkInterval?: number;
}

export const ApiStatus: React.FC<ApiStatusProps> = ({
  autoCheck = true,
  checkInterval = 10000,
}) => {
  const [status, setStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [latency, setLatency] = useState<number | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [diagnosticResult, setDiagnosticResult] = useState<Awaited<ReturnType<typeof runFullDiagnostics>> | null>(null);
  const [isRunningDiagnostics, setIsRunningDiagnostics] = useState(false);
  
  const config = getApiConfig();

  const checkConnection = useCallback(async () => {
    setStatus('checking');
    const result = await quickCheck();
    
    if (result.connected) {
      setStatus('connected');
      setLatency(result.latency || null);
    } else {
      setStatus('disconnected');
      setLatency(null);
    }
  }, []);

  const runDiagnostics = useCallback(async () => {
    setIsRunningDiagnostics(true);
    const result = await runFullDiagnostics();
    setDiagnosticResult(result);
    setIsRunningDiagnostics(false);
    
    // 更新状态
    const errorCount = result.checks.filter(c => c.status === 'error').length;
    if (errorCount === 0) {
      setStatus('connected');
    } else {
      setStatus('disconnected');
    }
  }, []);

  useEffect(() => {
    checkConnection();
    
    if (autoCheck) {
      const timer = setInterval(checkConnection, checkInterval);
      return () => clearInterval(timer);
    }
  }, [autoCheck, checkInterval, checkConnection]);

  // 当显示详情时运行完整诊断
  useEffect(() => {
    if (showDetails && !diagnosticResult) {
      runDiagnostics();
    }
  }, [showDetails, diagnosticResult, runDiagnostics]);

  return (
    <div className="api-status">
      <button 
        className={`status-indicator ${status}`}
        onClick={() => setShowDetails(!showDetails)}
        title="点击显示诊断详情"
      >
        <Server size={14} />
        {status === 'checking' && <Loader2 size={12} className="spin" />}
        {status === 'connected' && <CheckCircle size={12} />}
        {status === 'disconnected' && <AlertCircle size={12} />}
        <span className="status-text">
          {status === 'checking' && '检查中...'}
          {status === 'connected' && `已连接 ${latency ? `(${latency}ms)` : ''}`}
          {status === 'disconnected' && '未连接'}
        </span>
      </button>

      {showDetails && (
        <div className="status-details">
          <div className="details-header">
            <h4>API 连接诊断</h4>
            <button 
              className="btn-icon"
              onClick={runDiagnostics}
              disabled={isRunningDiagnostics}
              title="重新诊断"
            >
              <RefreshCw size={14} className={isRunningDiagnostics ? 'spin' : ''} />
            </button>
          </div>

          <div className="detail-section">
            <h5>配置信息</h5>
            <div className="detail-item">
              <span className="detail-label">API 地址:</span>
              <code className="detail-value">{config.baseUrl}</code>
            </div>
            <div className="detail-item">
              <span className="detail-label">后端地址:</span>
              <code className="detail-value">{config.backendUrl}</code>
            </div>
            <div className="detail-item">
              <span className="detail-label">运行模式:</span>
              <span className="detail-value">{config.mode}</span>
            </div>
          </div>

          {diagnosticResult && (
            <>
              <div className="detail-section">
                <h5>诊断结果</h5>
                <div className={`summary-box ${diagnosticResult.checks.some(c => c.status === 'error') ? 'error' : 'success'}`}>
                  {diagnosticResult.summary}
                </div>
                
                <div className="checks-list">
                  {diagnosticResult.checks.map((check, idx) => (
                    <div key={idx} className={`check-item ${check.status}`}>
                      <span className="check-icon">
                        {check.status === 'ok' && '✅'}
                        {check.status === 'warning' && '⚠️'}
                        {check.status === 'error' && '❌'}
                      </span>
                      <span className="check-name">{check.name}</span>
                      <span className="check-message">{check.message}</span>
                    </div>
                  ))}
                </div>
              </div>

              {diagnosticResult.recommendations.length > 0 && (
                <div className="detail-section">
                  <h5>修复建议</h5>
                  <ol className="recommendations-list">
                    {diagnosticResult.recommendations.map((rec, idx) => (
                      <li key={idx}>{rec}</li>
                    ))}
                  </ol>
                </div>
              )}
            </>
          )}

          <div className="detail-section">
            <h5>快速操作</h5>
            <div className="quick-actions">
              <button className="btn-action" onClick={checkConnection}>
                <RefreshCw size={12} /> 刷新状态
              </button>
              <button 
                className="btn-action secondary"
                onClick={() => {
                  console.clear();
                  import('../../../utils/api/apiDebug').then(m => m.printDiagnostics());
                }}
              >
                <Terminal size={12} /> 控制台诊断
              </button>
            </div>
          </div>

          <div className="help-text">
            <p><strong>常见问题：</strong></p>
            <ul>
              <li>确保后端服务已启动在 http://localhost:8000</li>
              <li>检查防火墙是否阻止了 8000 端口</li>
              <li>查看浏览器控制台获取详细错误信息</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default ApiStatus;
