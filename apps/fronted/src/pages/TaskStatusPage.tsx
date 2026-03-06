import React, { useState, useEffect } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { Loader2, CheckCircle2, XCircle, Clock, FileText, Calendar, Clock3, HardDrive, ArrowRight, Copy, Check } from 'lucide-react';
import { useAppStore } from '../stores';
import './TaskStatusPage.css';

const formatFileSize = (bytes?: number): string => {
  if (!bytes || bytes === 0) return '-';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatDuration = (seconds?: number): string => {
  if (!seconds || seconds === 0) return '-';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}分${s}秒`;
};

const formatTime = (isoString?: string): string => {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleString('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

const STATUS_CONFIG: Record<string, {
  label: string;
  color: string;
  bgColor: string;
  icon: React.ReactNode;
  description: string;
}> = {
  PENDING: {
    label: '等待中',
    color: '#f59e0b',
    bgColor: '#fffbeb',
    icon: <Clock size={20} />,
    description: '任务正在排队等待处理',
  },
  STARTED: {
    label: '处理中',
    color: '#3b82f6',
    bgColor: '#eff6ff',
    icon: <Loader2 size={20} className="spin" />,
    description: '正在分析文档，请稍候',
  },
  SUCCESS: {
    label: '已完成',
    color: '#10b981',
    bgColor: '#ecfdf5',
    icon: <CheckCircle2 size={20} />,
    description: '文档处理完成，可以查看结果',
  },
  FAILURE: {
    label: '失败',
    color: '#ef4444',
    bgColor: '#fef2f2',
    icon: <XCircle size={20} />,
    description: '处理过程中出现错误',
  },
  RETRY: {
    label: '重试中',
    color: '#8b5cf6',
    bgColor: '#f5f3ff',
    icon: <Loader2 size={20} className="spin" />,
    description: '正在重新尝试处理',
  },
  REVOKED: {
    label: '已取消',
    color: '#6b7280',
    bgColor: '#f9fafb',
    icon: <XCircle size={20} />,
    description: '任务已被取消',
  },
};

const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  return (
    <button className="copy-btn" onClick={handleCopy} title="复制">
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
};

const TaskStatusPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const taskId = searchParams.get('taskId');
  const navigate = useNavigate();

  const selectedTask = useAppStore(s => s.selectedTask);
  const selectedTaskLoading = useAppStore(s => s.selectedTaskLoading);
  const selectedTaskError = useAppStore(s => s.selectedTaskError);
  const fetchTask = useAppStore(s => s.fetchTask);
  const startTaskPolling = useAppStore(s => s.startTaskPolling);
  const stopTaskPolling = useAppStore(s => s.stopTaskPolling);
  const clearSelectedTask = useAppStore(s => s.clearSelectedTask);
  const notifySuccess = useAppStore(s => s.notifySuccess);

  useEffect(() => {
    if (!taskId) return;

    fetchTask(taskId);
    startTaskPolling(taskId);

    return () => {
      stopTaskPolling(taskId);
      clearSelectedTask();
    };
  }, [taskId, fetchTask, startTaskPolling, stopTaskPolling, clearSelectedTask]);

  useEffect(() => {
    if (selectedTask?.status === 'SUCCESS' && selectedTask.document_id) {
      const timer = setTimeout(() => {
        navigate(`/results/${selectedTask.document_id}`);
      }, 1500);
      
      notifySuccess('任务处理完成！');
      return () => clearTimeout(timer);
    }
  }, [selectedTask?.status, selectedTask?.document_id, navigate, notifySuccess]);

  const statusConfig = selectedTask?.status ? STATUS_CONFIG[selectedTask.status] || STATUS_CONFIG.PENDING : null;

  if (!taskId) {
    return (
      <div className="task-status-page">
        <div className="container">
          <div className="error-card">
            <XCircle size={48} className="error-icon" />
            <h2>缺少任务ID</h2>
            <p>无法获取任务状态，请从任务列表页面进入</p>
            <Link to="/tasks" className="btn-primary">
              前往任务列表
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (selectedTaskLoading && !selectedTask) {
    return (
      <div className="task-status-page">
        <div className="container">
          <div className="loading-card">
            <Loader2 size={48} className="spin" />
            <h2>正在获取任务状态...</h2>
          </div>
        </div>
      </div>
    );
  }

  if (selectedTaskError && !selectedTask) {
    return (
      <div className="task-status-page">
        <div className="container">
          <div className="error-card">
            <XCircle size={48} className="error-icon" />
            <h2>获取失败</h2>
            <p>{selectedTaskError}</p>
            <div className="button-group">
              <button className="btn-primary" onClick={() => fetchTask(taskId)}>
                重试
              </button>
              <Link to="/tasks" className="btn-secondary">
                返回任务列表
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!selectedTask) return null;

  return (
    <div className="task-status-page">
      <div className="container">
        <header className="page-header">
          <h1>任务状态</h1>
          <p className="task-id">
            任务ID: <code>{selectedTask.task_id}</code>
            <CopyButton text={selectedTask.task_id} />
          </p>
        </header>

        <div 
          className="status-card"
          style={{ 
            borderColor: statusConfig?.color,
            backgroundColor: statusConfig?.bgColor 
          }}
        >
          <div className="status-icon" style={{ color: statusConfig?.color }}>
            {statusConfig?.icon}
          </div>
          <div className="status-content">
            <h2 style={{ color: statusConfig?.color }}>
              {statusConfig?.label}
            </h2>
            <p>{statusConfig?.description}</p>
          </div>
        </div>

        {selectedTask.status === 'SUCCESS' && selectedTask.document_id && (
          <div className="info-card success">
            <h3>
              <CheckCircle2 size={20} />
              处理完成
            </h3>
            
            <div className="info-grid">
              <div className="info-item">
                <span className="label">文档ID</span>
                <div className="value-with-copy">
                  <code className="value">{selectedTask.document_id}</code>
                  <CopyButton text={selectedTask.document_id} />
                </div>
              </div>

              <div className="info-item">
                <span className="label">
                  <HardDrive size={14} />
                  文件大小
                </span>
                <span className="value">{formatFileSize(selectedTask.file_size_bytes)}</span>
              </div>

              <div className="info-item">
                <span className="label">
                  <Clock3 size={14} />
                  处理耗时
                </span>
                <span className="value">{formatDuration(selectedTask.processing_duration_seconds)}</span>
              </div>

              <div className="info-item">
                <span className="label">
                  <Calendar size={14} />
                  创建时间
                </span>
                <span className="value">{formatTime(selectedTask.created_at)}</span>
              </div>

              <div className="info-item">
                <span className="label">
                  <Clock size={14} />
                  更新时间
                </span>
                <span className="value">{formatTime(selectedTask.updated_at)}</span>
              </div>
            </div>

            <div className="action-section">
              <Link 
                to={`/results/${selectedTask.document_id}`} 
                className="btn-view-report"
              >
                <FileText size={18} />
                查看完整评级报告
                <ArrowRight size={18} />
              </Link>
            </div>
          </div>
        )}

        {selectedTask.status === 'FAILURE' && selectedTask.error && (
          <div className="info-card error">
            <h3>
              <XCircle size={20} />
              处理失败
            </h3>
            <div className="error-message">
              <strong>错误信息：</strong>
              <pre>{selectedTask.error}</pre>
            </div>
            <div className="button-group">
              <button className="btn-primary" onClick={() => fetchTask(taskId)}>
                重试
              </button>
              <Link to="/pdf/upload" className="btn-secondary">
                重新上传
              </Link>
            </div>
          </div>
        )}

        {(selectedTask.status === 'PENDING' || selectedTask.status === 'STARTED' || selectedTask.status === 'RETRY') && (
          <div className="processing-info">
            <Loader2 size={24} className="spin" />
            <p>正在处理中，请稍候...</p>
            <div className="progress-bar">
              <div className="progress-indeterminate" />
            </div>
          </div>
        )}

        <div className="page-footer">
          <Link to="/tasks" className="btn-secondary">
            返回任务列表
          </Link>
        </div>
      </div>
    </div>
  );
};

export default TaskStatusPage;