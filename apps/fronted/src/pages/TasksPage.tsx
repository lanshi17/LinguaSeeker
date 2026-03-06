import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  Plus, Search, Filter, RefreshCw, CheckCircle2, XCircle, Clock, 
  Loader2, ChevronLeft, ChevronRight, Trash2, X
} from 'lucide-react';
import { useAppStore } from '../stores';
import type { TaskSummary } from '../types/api';
import './TasksPage.css';

type StatusType = 'all' | 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED';

const STATUS_CONFIG: Record<string, {
  label: string;
  color: string;
  bgColor: string;
  icon: React.ReactNode;
}> = {
  PENDING: { label: '等待中', color: '#f59e0b', bgColor: '#fffbeb', icon: <Clock size={16} /> },
  STARTED: { label: '处理中', color: '#3b82f6', bgColor: '#eff6ff', icon: <Loader2 size={16} className="spin" /> },
  SUCCESS: { label: '已完成', color: '#10b981', bgColor: '#ecfdf5', icon: <CheckCircle2 size={16} /> },
  FAILURE: { label: '失败', color: '#ef4444', bgColor: '#fef2f2', icon: <XCircle size={16} /> },
  RETRY: { label: '重试中', color: '#8b5cf6', bgColor: '#f5f3ff', icon: <Loader2 size={16} className="spin" /> },
  REVOKED: { label: '已取消', color: '#6b7280', bgColor: '#f9fafb', icon: <XCircle size={16} /> },
};

const ITEMS_PER_PAGE = 10;

const formatTime = (isoString?: string): string => {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
};

const TasksPage: React.FC = () => {
  const [currentPage, setCurrentPage] = useState(1);
  const prevProcessingTasksRef = useRef<Set<string>>(new Set());

  const tasks = useAppStore(s => s.tasks);
  const tasksLoading = useAppStore(s => s.tasksLoading);
  const tasksError = useAppStore(s => s.tasksError);
  const lastTasksUpdate = useAppStore(s => s.lastTasksUpdate);
  const taskFilters = useAppStore(s => s.taskFilters);
  const selectedTaskIds = useAppStore(s => s.selectedTaskIds);
  
  const fetchTasks = useAppStore(s => s.fetchTasks);
  const startTasksListPolling = useAppStore(s => s.startTasksListPolling);
  const stopTasksListPolling = useAppStore(s => s.stopTasksListPolling);
  const setTaskFilter = useAppStore(s => s.setTaskFilter);
  const toggleTaskSelection = useAppStore(s => s.toggleTaskSelection);
  const selectAllTasks = useAppStore(s => s.selectAllTasks);
  const clearTaskSelection = useAppStore(s => s.clearTaskSelection);
  const notifySuccess = useAppStore(s => s.notifySuccess);
  const notifyError = useAppStore(s => s.notifyError);

  const filteredTasks = useMemo(() => {
    let result = [...tasks];
    
    if (taskFilters.status && taskFilters.status !== 'all') {
      result = result.filter(t => t.status === taskFilters.status);
    }
    
    if (taskFilters.searchQuery) {
      const query = taskFilters.searchQuery.toLowerCase();
      result = result.filter(t => 
        t.task_id.toLowerCase().includes(query)
      );
    }
    
    if (taskFilters.dateFilter && taskFilters.dateFilter !== 'all') {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
      const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
      
      result = result.filter(t => {
        const created = new Date(t.created_at);
        switch (taskFilters.dateFilter) {
          case 'today': return created >= today;
          case 'week': return created >= weekAgo;
          case 'month': return created >= monthAgo;
          default: return true;
        }
      });
    }
    
    return result;
  }, [tasks, taskFilters]);

  const totalPages = Math.ceil(filteredTasks.length / ITEMS_PER_PAGE);
  const paginatedTasks = filteredTasks.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  useEffect(() => {
    fetchTasks();
    startTasksListPolling();
    
    return () => {
      stopTasksListPolling();
    };
  }, [fetchTasks, startTasksListPolling, stopTasksListPolling]);

  useEffect(() => {
    const currentProcessing = new Set(
      tasks.filter(t => t.status === 'STARTED').map(t => t.task_id)
    );
    
    currentProcessing.forEach(taskId => {
      if (!prevProcessingTasksRef.current.has(taskId)) {
      }
    });
    
    prevProcessingTasksRef.current.forEach(taskId => {
      if (!currentProcessing.has(taskId)) {
        const task = tasks.find(t => t.task_id === taskId);
        if (task) {
          if (task.status === 'SUCCESS') {
            notifySuccess(`任务 ${taskId.slice(0, 8)} 已完成`);
          } else if (task.status === 'FAILURE') {
            notifyError(`任务 ${taskId.slice(0, 8)} 失败`);
          }
        }
      }
    });
    
    prevProcessingTasksRef.current = currentProcessing;
  }, [tasks, notifySuccess, notifyError]);

  useEffect(() => {
    setCurrentPage(1);
  }, [taskFilters]);

  const handleSelectAll = () => {
    if (selectedTaskIds.length === filteredTasks.length) {
      clearTaskSelection();
    } else {
      selectAllTasks(filteredTasks.map(t => t.task_id));
    }
  };

  const handleRefresh = () => {
    fetchTasks();
  };

  const stats = useMemo(() => {
    const result: Record<string, number> = { all: tasks.length };
    tasks.forEach(t => {
      result[t.status] = (result[t.status] || 0) + 1;
    });
    return result;
  }, [tasks]);

  return (
    <div className="tasks-page">
      <div className="container">
        <header className="page-header">
          <div className="header-content">
            <h1>任务列表</h1>
            {lastTasksUpdate && (
              <span className="last-updated">
                最后更新: {lastTasksUpdate.toLocaleTimeString('zh-CN')}
              </span>
            )}
          </div>
          <Link to="/pdf/upload" className="btn-primary">
            <Plus size={18} />
            上传PDF
          </Link>
        </header>

        <div className="stats-bar">
          {(Object.keys(STATUS_CONFIG) as StatusType[]).map(status => (
            <button
              key={status}
              className={`stat-chip ${taskFilters.status === status ? 'active' : ''}`}
              onClick={() => setTaskFilter('status', status)}
            >
              <span className="stat-label">{STATUS_CONFIG[status]?.label || status}</span>
              <span className="stat-count">{stats[status] || 0}</span>
            </button>
          ))}
        </div>

        <div className="filters-bar">
          <div className="search-box">
            <Search size={18} className="search-icon" />
            <input
              type="text"
              placeholder="搜索任务ID..."
              value={taskFilters.searchQuery}
              onChange={(e) => setTaskFilter('searchQuery', e.target.value)}
            />
          </div>

          <select
            value={taskFilters.dateFilter}
            onChange={(e) => setTaskFilter('dateFilter', e.target.value)}
            className="date-filter"
          >
            <option value="all">全部时间</option>
            <option value="today">今天</option>
            <option value="week">最近一周</option>
            <option value="month">最近一月</option>
          </select>

          <button className="btn-icon" onClick={handleRefresh} title="刷新">
            <RefreshCw size={18} />
          </button>
        </div>

        {tasksError && (
          <div className="error-banner">
            <XCircle size={20} />
            <span>{tasksError}</span>
            <button onClick={handleRefresh}>重试</button>
          </div>
        )}

        {tasksLoading && tasks.length === 0 ? (
          <div className="loading-state">
            <Loader2 size={48} className="spin" />
            <p>加载任务列表...</p>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="empty-state">
            {taskFilters.status !== 'all' || taskFilters.searchQuery || taskFilters.dateFilter !== 'all' ? (
              <>
                <Filter size={48} />
                <h3>没有匹配的任务</h3>
                <p>尝试调整筛选条件</p>
                <button 
                  className="btn-secondary"
                  onClick={() => {
                    setTaskFilter('status', 'all');
                    setTaskFilter('searchQuery', '');
                    setTaskFilter('dateFilter', 'all');
                  }}
                >
                  清除筛选
                </button>
              </>
            ) : (
              <>
                <Plus size={48} />
                <h3>暂无任务</h3>
                <p>上传PDF开始创建任务</p>
                <Link to="/pdf/upload" className="btn-primary">
                  上传PDF
                </Link>
              </>
            )}
          </div>
        ) : (
          <>
            <div className="tasks-list">
              <div className="list-header">
                <div className="col-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedTaskIds.length === filteredTasks.length && filteredTasks.length > 0}
                    onChange={handleSelectAll}
                  />
                </div>
                <div className="col-task-id">任务ID</div>
                <div className="col-status">状态</div>
                <div className="col-created">创建时间</div>
                <div className="col-updated">更新时间</div>
                <div className="col-actions">操作</div>
              </div>

              {paginatedTasks.map(task => {
                const config = STATUS_CONFIG[task.status] || STATUS_CONFIG.PENDING;
                const isSelected = selectedTaskIds.includes(task.task_id);
                
                return (
                  <div key={task.task_id} className={`task-row ${isSelected ? 'selected' : ''}`}>
                    <div className="col-checkbox">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleTaskSelection(task.task_id)}
                      />
                    </div>
                    <div className="col-task-id">
                      <Link to={`/tasks/status?taskId=${task.task_id}`} className="task-link">
                        {task.task_id}
                      </Link>
                    </div>
                    <div className="col-status">
                      <span 
                        className="status-badge" 
                        style={{ color: config.color, backgroundColor: config.bgColor }}
                      >
                        {config.icon}
                        {config.label}
                      </span>
                    </div>
                    <div className="col-created">{formatTime(task.created_at)}</div>
                    <div className="col-updated">{formatTime(task.updated_at)}</div>
                    <div className="col-actions">
                      {task.status === 'SUCCESS' && (
                        <Link 
                          to={`/results/${task.document_id}`}
                          className="btn-small btn-primary"
                        >
                          查看结果
                        </Link>
                      )}
                      {task.status === 'FAILURE' && (
                        <Link 
                          to={`/tasks/status?taskId=${task.task_id}`}
                          className="btn-small btn-secondary"
                        >
                          查看详情
                        </Link>
                      )}
                      {(task.status === 'PENDING' || task.status === 'STARTED') && (
                        <Link 
                          to={`/tasks/status?taskId=${task.task_id}`}
                          className="btn-small btn-secondary"
                        >
                          查看进度
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="btn-icon"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={18} />
                </button>
                
                <span className="page-info">
                  第 {currentPage} / {totalPages} 页 ({filteredTasks.length} 条记录)
                </span>
                
                <button
                  className="btn-icon"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default TasksPage;