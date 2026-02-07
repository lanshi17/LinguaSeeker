/**
 * 任务状态面板组件
 */
import React from 'react';
import { 
  X, 
  Loader2, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  FileText, 
  Link, 
  Trash2,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import type { Task } from '../../../types/task';
import { TaskStatus, TaskType } from '../../../types/task';
import './TaskPanel.css';

interface TaskPanelProps {
  tasks: Task[];
  onRemoveTask: (taskId: string) => void;
  onClearCompleted: () => void;
  onTaskClick?: (task: Task) => void;
  isOpen: boolean;
  onToggle: () => void;
}

const typeIcons: Record<string, React.ReactNode> = {
  [TaskType.PDF_UPLOAD]: <FileText size={14} />,
  [TaskType.PMID_FETCH]: <FileText size={14} />,
  [TaskType.DOI_FETCH]: <Link size={14} />,
  [TaskType.URL_FETCH]: <Link size={14} />,
};

const typeNames: Record<string, string> = {
  [TaskType.PDF_UPLOAD]: 'PDF上传',
  [TaskType.PMID_FETCH]: 'PMID获取',
  [TaskType.DOI_FETCH]: 'DOI获取',
  [TaskType.URL_FETCH]: 'URL获取',
};

const statusConfig: Record<string, { icon: React.ReactNode; label: string; className: string }> = {
  [TaskStatus.PENDING]: { 
    icon: <Clock size={14} />, 
    label: '等待中', 
    className: 'status-pending' 
  },
  [TaskStatus.PROCESSING]: { 
    icon: <Loader2 size={14} className="spin" />, 
    label: '处理中', 
    className: 'status-processing' 
  },
  [TaskStatus.COMPLETED]: { 
    icon: <CheckCircle2 size={14} />, 
    label: '已完成', 
    className: 'status-completed' 
  },
  [TaskStatus.FAILED]: { 
    icon: <AlertCircle size={14} />, 
    label: '失败', 
    className: 'status-failed' 
  },
};

export const TaskPanel: React.FC<TaskPanelProps> = ({
  tasks,
  onRemoveTask,
  onClearCompleted,
  onTaskClick,
  isOpen,
  onToggle,
}) => {
  const activeTasks = tasks.filter(t => t.status === TaskStatus.PENDING || t.status === TaskStatus.PROCESSING);
  const completedTasks = tasks.filter(t => t.status === TaskStatus.COMPLETED);
  const failedTasks = tasks.filter(t => t.status === TaskStatus.FAILED);

  const renderTask = (task: Task) => {
    const status = statusConfig[task.status];
    const canNavigate = task.status === TaskStatus.COMPLETED && task.result?.docId;

    return (
      <div 
        key={task.id} 
        className={`task-item ${canNavigate ? 'clickable' : ''}`}
        onClick={() => canNavigate && onTaskClick?.(task)}
      >
        <div className="task-icon">
          {typeIcons[task.type]}
        </div>
        <div className="task-content">
          <div className="task-header">
            <span className="task-title">{task.title}</span>
            <span className={`task-status ${status.className}`}>
              {status.icon}
              {status.label}
            </span>
          </div>
          {task.description && (
            <p className="task-description">{task.description}</p>
          )}
          {task.status === TaskStatus.PROCESSING && task.progress !== undefined && (
            <div className="task-progress">
              <div className="progress-bar">
                <div 
                  className="progress-fill" 
                  style={{ width: `${task.progress}%` }}
                />
              </div>
              <span className="progress-text">{task.progress}%</span>
            </div>
          )}
          {task.error && (
            <p className="task-error">{task.error}</p>
          )}
          <div className="task-meta">
            <span className="task-type">{typeNames[task.type]}</span>
            <span className="task-time">
              {new Date(task.updatedAt).toLocaleTimeString()}
            </span>
          </div>
        </div>
        <button 
          className="task-remove"
          onClick={(e) => {
            e.stopPropagation();
            onRemoveTask(task.id);
          }}
        >
          <X size={14} />
        </button>
      </div>
    );
  };

  if (!isOpen) {
    const totalCount = tasks.length;
    const activeCount = activeTasks.length;

    return (
      <button className="task-panel-collapsed" onClick={onToggle}>
        <div className="collapsed-icon">
          {activeCount > 0 ? <Loader2 size={18} className="spin" /> : <Clock size={18} />}
        </div>
        <span className="collapsed-text">
          {activeCount > 0 ? `${activeCount} 个任务处理中` : `任务历史 (${totalCount})`}
        </span>
        <ChevronUp size={16} />
      </button>
    );
  }

  return (
    <div className="task-panel">
      <div className="task-panel-header">
        <div className="header-title">
          <Clock size={18} />
          <span>任务状态</span>
          {activeTasks.length > 0 && (
            <span className="badge active">{activeTasks.length}</span>
          )}
        </div>
        <div className="header-actions">
          {completedTasks.length > 0 && (
            <button 
              className="clear-btn"
              onClick={onClearCompleted}
              title="清空已完成"
            >
              <Trash2 size={14} />
            </button>
          )}
          <button className="toggle-btn" onClick={onToggle}>
            <ChevronDown size={16} />
          </button>
        </div>
      </div>

      <div className="task-panel-content">
        {tasks.length === 0 ? (
          <div className="empty-tasks">
            <Clock size={32} className="empty-icon" />
            <p>暂无任务</p>
            <span>上传PDF或输入文献ID开始分析</span>
          </div>
        ) : (
          <>
            {activeTasks.length > 0 && (
              <div className="task-section">
                <h4 className="section-title">进行中</h4>
                {activeTasks.map(renderTask)}
              </div>
            )}
            
            {failedTasks.length > 0 && (
              <div className="task-section">
                <h4 className="section-title">失败</h4>
                {failedTasks.map(renderTask)}
              </div>
            )}
            
            {completedTasks.length > 0 && (
              <div className="task-section">
                <h4 className="section-title">已完成</h4>
                {completedTasks.map(renderTask)}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
