/**
 * Task Status Page
 * 显示任务处理状态和进度
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLoaderData, useSearchParams } from 'react-router-dom';
import { 
  Loader2, 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  ArrowLeft,
  RefreshCw,
  Clock,
  FileCode,
  Eye
} from 'lucide-react';
import { useTaskPolling } from '../../hooks/useTaskPolling';
import { useTaskWebSocket } from '../../hooks/useWebSocket';
import { retryTask, cancelTask } from '../../services/api';
import type { EvidenceItemSummary } from '../../types';
import './TaskStatusPage.css';

interface LoaderData {
  taskId: string | null;
}

/**
 * 获取状态图标
 */
const getStatusIcon = (status: string) => {
  switch (status) {
    case 'pending':
      return <Clock size={24} className="status-icon pending" />;
    case 'processing':
      return <Loader2 size={24} className="status-icon processing spin" />;
    case 'completed':
      return <CheckCircle size={24} className="status-icon completed" />;
    case 'failed':
      return <XCircle size={24} className="status-icon failed" />;
    case 'cancelled':
      return <AlertCircle size={24} className="status-icon cancelled" />;
    default:
      return <Clock size={24} className="status-icon" />;
  }
};

/**
 * 获取状态文本
 */
const getStatusText = (status: string): string => {
  switch (status) {
    case 'pending': return '等待处理';
    case 'processing': return '处理中';
    case 'completed': return '已完成';
    case 'failed': return '处理失败';
    case 'cancelled': return '已取消';
    default: return status;
  }
};

/**
 * 格式化时间
 */
const formatTime = (dateStr: string | null): string => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN');
};

/**
 * 格式化时长
 */
const formatDuration = (seconds: number | null): string => {
  if (!seconds) return '-';
  if (seconds < 60) return `${Math.round(seconds)}秒`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}分${remainingSeconds}秒`;
};

/**
 * 证据项卡片
 */
const EvidenceItemCard: React.FC<{ item: EvidenceItemSummary }> = ({ item }) => (
  <div className={`evidence-item ${item.review_required ? 'review-required' : ''}`}>
    <div className="evidence-header">
      <span className="evidence-code">{item.acmg_code}</span>
      {item.review_required && (
        <span className="review-badge">需审核</span>
      )}
    </div>
    <div className="evidence-meta">
      <span className="confidence-score">
        置信度: {(item.confidence_score * 100).toFixed(1)}%
      </span>
      <span className="source-page">第 {item.source_page} 页</span>
    </div>
  </div>
);

export const TaskStatusPage: React.FC = () => {
  const navigate = useNavigate();
  const loaderData = useLoaderData() as LoaderData;
  const [searchParams] = useSearchParams();
  const taskId = loaderData.taskId || searchParams.get('taskId');
  
  const [isRetrying, setIsRetrying] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [useWebSocket, setUseWebSocket] = useState(true); // 默认使用 WebSocket
  
  // WebSocket 连接
  const {
    isConnected: wsConnected,
    progress: wsProgress,
    currentStage: wsStage,
    lastMessage,
  } = useTaskWebSocket(
    useWebSocket ? taskId : null,
    {
      enabled: useWebSocket,
      onProgress: (progress, stage) => {
        console.log(`[WebSocket] 进度更新: ${progress}%`, stage);
      },
      onComplete: (data) => {
        console.log('[WebSocket] 任务完成:', data);
      },
      onError: (error) => {
        console.error('[WebSocket] 错误:', error);
        // WebSocket 失败时切换到轮询
        setUseWebSocket(false);
      },
    }
  );

  // 轮询作为后备方案
  const { status: pollStatus, isPolling, error, startPolling, stopPolling } = useTaskPolling(
    undefined,
    (completedStatus) => {
      if (completedStatus.status === 'completed') {
        // 任务完成后，可以选择自动跳转
        // navigate(`/analysis/${completedStatus.document_id}`);
      }
    },
    (err) => {
      console.error('Task polling error:', err);
    },
    { interval: 2000 }
  );

  // 合并状态：优先使用 WebSocket 数据，如果没有则使用轮询数据
  const status = lastMessage?.data || pollStatus;
  
  // 计算进度：优先使用 WebSocket 进度
  const progressPercentage = wsConnected && wsProgress > 0 
    ? wsProgress 
    : (status?.progress_percentage || 0);
  
  // 计算当前阶段
  const currentStage = wsConnected && wsStage 
    ? wsStage 
    : status?.current_stage;

  // 开始监控
  useEffect(() => {
    if (taskId) {
      if (useWebSocket) {
        // WebSocket 会自动连接
        console.log('[TaskStatus] 使用 WebSocket 监控任务:', taskId);
      } else {
        // 使用轮询
        console.log('[TaskStatus] 使用轮询监控任务:', taskId);
        startPolling(taskId);
      }
    }
    return () => {
      stopPolling();
    };
  }, [taskId, useWebSocket, startPolling, stopPolling]);

  // 重试任务
  const handleRetry = async () => {
    if (!taskId) return;
    setIsRetrying(true);
    try {
      await retryTask(taskId);
      // 重新开始轮询
      startPolling(taskId);
    } catch (err) {
      console.error('Retry failed:', err);
      alert('重试失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setIsRetrying(false);
    }
  };

  // 取消任务
  const handleCancel = async () => {
    if (!taskId) return;
    setIsCancelling(true);
    try {
      await cancelTask(taskId);
      stopPolling();
    } catch (err) {
      console.error('Cancel failed:', err);
      alert('取消失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setIsCancelling(false);
    }
  };

  // 查看文档
  const handleViewDocument = () => {
    if (status?.document_id) {
      navigate(`/analysis/${status.document_id}`);
    }
  };

  if (!taskId) {
    return (
      <div className="task-status-page">
        <div className="error-container">
          <AlertCircle size={48} className="error-icon" />
          <h2>缺少任务ID</h2>
          <p>请提供有效的任务ID</p>
          <button className="btn-primary" onClick={() => navigate(-1)}>
            <ArrowLeft size={16} /> 返回
          </button>
        </div>
      </div>
    );
  }

  if (error && !status) {
    return (
      <div className="task-status-page">
        <div className="error-container">
          <XCircle size={48} className="error-icon" />
          <h2>加载失败</h2>
          <p>{error.message}</p>
          <button className="btn-primary" onClick={() => startPolling(taskId)}>
            <RefreshCw size={16} /> 重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="task-status-page">
      <div className="task-status-container">
        {/* 头部 */}
        <header className="task-header">
          <button className="btn-back" onClick={() => navigate(-1)}>
            <ArrowLeft size={20} />
          </button>
          <h1>任务状态</h1>
        </header>

        {/* 状态概览 */}
        <div className={`status-overview ${status?.status || 'loading'}`}>
          <div className="status-icon-wrapper">
            {getStatusIcon(status?.status || 'pending')}
          </div>
          <div className="status-info">
            <h2>{getStatusText(status?.status || 'pending')}</h2>
            {(currentStage || status?.current_stage) && (
              <p className="current-stage">{currentStage || status?.current_stage}</p>
            )}
          </div>
        </div>

        {/* WebSocket 连接状态 */}
        <div className="websocket-status">
          {wsConnected ? (
            <span className="ws-connected">
              ● 实时推送已连接
            </span>
          ) : useWebSocket ? (
            <span className="ws-connecting">
              ○ 正在连接实时推送...
            </span>
          ) : (
            <span className="ws-polling">
              ○ 使用轮询模式
              <button 
                className="btn-retry-ws"
                onClick={() => setUseWebSocket(true)}
              >
                重试连接
              </button>
            </span>
          )}
        </div>

        {/* 进度条 */}
        <div className="progress-section">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
          <span className="progress-text">
            {progressPercentage}%
          </span>
        </div>

        {/* 任务详情 */}
        {status && (
          <div className="task-details">
            <div className="detail-grid">
              <div className="detail-item">
                <span className="detail-label">任务ID</span>
                <span className="detail-value task-id">{status.task_id}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">文档ID</span>
                <span className="detail-value">{status.document_id}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">文件大小</span>
                <span className="detail-value">
                  {status.file_size_bytes 
                    ? `${(status.file_size_bytes / 1024 / 1024).toFixed(2)} MB`
                    : '-'
                  }
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">处理时长</span>
                <span className="detail-value">
                  {formatDuration(status.processing_time_seconds)}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">创建时间</span>
                <span className="detail-value">{formatTime(status.created_at)}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">更新时间</span>
                <span className="detail-value">{formatTime(status.updated_at)}</span>
              </div>
              {status.completed_at && (
                <div className="detail-item">
                  <span className="detail-label">完成时间</span>
                  <span className="detail-value">{formatTime(status.completed_at)}</span>
                </div>
              )}
            </div>

            {/* 错误信息 */}
            {status.error_message && (
              <div className="error-message">
                <AlertCircle size={20} />
                <p>{status.error_message}</p>
              </div>
            )}
          </div>
        )}

        {/* 证据项列表 */}
        {status && status.evidence_items && status.evidence_items.length > 0 && (
          <div className="evidence-section">
            <h3>
              <FileCode size={20} />
              提取的证据项 ({status.evidence_items.length})
            </h3>
            <div className="evidence-list">
              {status.evidence_items.map((item) => (
                <EvidenceItemCard key={item.id} item={item} />
              ))}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="action-buttons">
          {status?.status === 'failed' && (
            <button 
              className="btn-primary" 
              onClick={handleRetry}
              disabled={isRetrying}
            >
              {isRetrying ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
              重试任务
            </button>
          )}
          
          {(status?.status === 'pending' || status?.status === 'processing') && (
            <button 
              className="btn-secondary" 
              onClick={handleCancel}
              disabled={isCancelling}
            >
              {isCancelling ? <Loader2 size={16} className="spin" /> : <XCircle size={16} />}
              取消任务
            </button>
          )}
          
          {status?.status === 'completed' && (
            <button className="btn-primary" onClick={handleViewDocument}>
              <Eye size={16} /> 查看文档
            </button>
          )}
        </div>

        {/* 轮询状态 */}
        {isPolling && (
          <div className="polling-indicator">
            <Loader2 size={14} className="spin" />
            <span>实时更新中...</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default TaskStatusPage;
