/**
 * Optimized Home Page
 * 
 * Features:
 * - Modern card-based layout
 * - Drag-and-drop upload
 * - Real-time input type detection
 * - Task status panel
 * - Feature comparison showcase
 */
import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload,
  FileText,
  Search,
  Network,
  ArrowRight,
  Loader2,
  Link2,
  AlertCircle,
  CheckCircle,
  Sparkles,
  BookOpen,
  MousePointerClick,
  Zap,
  MonitorSmartphone,
  ChevronRight,
  Eye,
  X,
  Microscope
} from 'lucide-react';
import {
  uploadPDFForm,
  fetchByPMID,
  fetchByDOI,
  pollTaskStatus
} from '../../services/api';
import { useTaskQueue } from '../../hooks/useTaskPolling';
import { ProxyDiagnostic } from '../../components/debug/ProxyDiagnostic/ProxyDiagnostic';
import { validatePDFFile, getUserFriendlyError } from '../../services/errorHandler';
import { calculateFileHash, formatFileSize } from '../../utils/helpers/fileUtils';
import type { TaskStatusResponse } from '../../types';
import './HomePage.css';

/**
 * Detect input type (PMID / DOI / URL)
 */
const detectInputType = (input: string): 'pmid' | 'doi' | 'url' | 'unknown' => {
  const trimmed = input.trim();
  if (/^\d+$/.test(trimmed)) return 'pmid';
  if (/^10\.\d{4,}\/.*/.test(trimmed)) return 'doi';
  if (/^https?:\/\//.test(trimmed)) return 'url';
  return 'unknown';
};

/**
 * Feature comparison data
 */
const features = [
  {
    icon: <BookOpen size={20} />,
    title: 'Semantic Chapter Alignment',
    desc: 'Fixes scroll misalignment caused by content length differences',
    detail: 'Chapter-level alignment + progress compensation'
  },
  {
    icon: <MousePointerClick size={20} />,
    title: 'Smart Chapter Tracking',
    desc: 'Precisely identifies currently visible chapters',
    detail: 'Real-time tracking via Intersection Observer'
  },
  {
    icon: <Zap size={20} />,
    title: 'High-Performance Sync',
    desc: 'Smooth scroll synchronization experience',
    detail: 'Debouncing + throttling + fallback strategies'
  },
  {
    icon: <MonitorSmartphone size={20} />,
    title: 'Responsive Design',
    desc: 'Adapts to different screen sizes',
    detail: 'Auto-switch to tab mode on small screens'
  },
  {
    icon: <Microscope size={20} />,
    title: 'Evidence Visualization',
    desc: 'Interactive medical evidence highlighting and analysis',
    detail: 'Four-pane layout with real-time evidence positioning'
  },
];

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { queue, activeCount, addTask, updateTaskProgress, removeTask } = useTaskQueue();
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  
  const [searchKeyword, setSearchKeyword] = useState('');
  const [textInput, setTextInput] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [activeTab, setActiveTab] = useState<'upload' | 'text'>('upload');
  const [showMoreFeatures, setShowMoreFeatures] = useState(false);
  
  const [processingInput, setProcessingInput] = useState(false);
  
  // 错误提示状态
  const [uploadError, setUploadError] = useState<{title: string; message: string; type: 'error' | 'warning' | 'info'; action?: string} | null>(null);
  
  // 统一使用 form-data 上传
  const useFormDataUpload = true;
  
  // 调试模式：强制上传（绕过重复检测）
  const [forceUpload, setForceUpload] = useState(false);
  
  // 当前上传文件信息（用于显示）
  const [currentFile, setCurrentFile] = useState<{name: string; size: string; hash: string} | null>(null);

  /**
   * 触发文件选择
   */
  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  /**
   * 处理文件上传
   */
  const handleFileUpload = useCallback(async (file: File) => {
    // 清除之前的错误和文件信息
    setUploadError(null);
    setCurrentFile(null);
    
    // 验证文件
    const validation = validatePDFFile(file);
    if (!validation.valid) {
      setUploadError({
        title: '文件验证失败',
        message: validation.error || '文件不符合要求',
        type: 'warning',
      });
      return;
    }

    // 计算文件 hash 用于调试
    const fileHash = await calculateFileHash(file);
    setCurrentFile({
      name: file.name,
      size: formatFileSize(file.size),
      hash: fileHash,
    });
    
    console.log('[Upload] 文件信息:', {
      name: file.name,
      size: formatFileSize(file.size),
      hash: fileHash,
      type: file.type,
    });

    const taskId = `upload-${Date.now()}`;
    addTask({ 
      id: taskId, 
      type: 'pdf_upload', 
      title: file.name,
      description: 'PDF 文件上传'
    });

    try {
      // 统一使用 form-data 方式上传
      console.log('[Upload] 使用 form-data 方式上传 (multipart/form-data)', { force: forceUpload });
      const response = await uploadPDFForm(file, 0, forceUpload, fileHash);

      // 开始轮询任务状态
      pollTaskStatus(
        response.task_id,
        (status) => {
          updateTaskProgress(taskId, status);
        }
      ).then((finalStatus) => {
        if (finalStatus.status === 'completed') {
          // 跳转到分析页面
          setTimeout(() => {
            navigate(`/analysis/${finalStatus.document_id}`);
          }, 1000);
        }
      });
    } catch (err) {
      const userError = getUserFriendlyError(err);
      
      // 控制台输出详细错误分类（用于调试）
      console.error('[Upload] 上传失败:', {
        type: userError.type,
        title: userError.title,
        description: userError.description,
        action: userError.action,
        file: currentFile,
        hash: fileHash, // 前端计算的 hash
        error: err,
      });
      
      // 特别输出 hash 调试信息（用于与后端对比）
      if (userError.type === 'warning' && userError.title === '文件已上传过') {
        console.warn('[Hash Debug] 检测到重复文件:');
        console.warn('  前端计算 Hash (SHA-256):', fileHash);
        console.warn('  文件名:', file.name);
        console.warn('  文件大小:', formatFileSize(file.size));
        console.warn('  请与后端日志中的 hash 值对比');
      }
      
      setUploadError({
        title: userError.title,
        message: userError.description,
        type: userError.type,
        action: userError.action,
      });
      
      updateTaskProgress(taskId, {
        task_id: taskId,
        document_id: '',
        status: 'failed',
        progress_percentage: 0,
        current_stage: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        completed_at: null,
        error_message: userError.description,
        evidence_items: [],
        processing_time_seconds: null,
        file_size_bytes: file.size,
      } as TaskStatusResponse);
    }
  }, [addTask, updateTaskProgress, navigate, useBinaryUpload, forceUpload]);

  /**
   * 处理拖拽
   */
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  /**
   * 处理文本输入提交 (PMID/DOI/URL)
   */
  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim()) return;

    const detectedType = detectInputType(textInput);
    if (detectedType === 'unknown') {
      alert('无法识别输入类型。请输入 PMID (纯数字)、DOI (10.xxx开头) 或 URL (http/https)');
      return;
    }
    
    setProcessingInput(true);
    const input = textInput.trim();
    
    const taskId = `${detectedType}-${Date.now()}`;
    
    addTask({ 
      id: taskId, 
      type: detectedType === 'pmid' ? 'pmid_fetch' : detectedType === 'doi' ? 'doi_fetch' : 'pmid_fetch',
      title: detectedType.toUpperCase(),
      description: input
    });

    try {
      let response;
      
      if (detectedType === 'pmid') {
        response = await fetchByPMID({ pmid: input });
      } else if (detectedType === 'doi') {
        response = await fetchByDOI({ doi: input });
      } else {
        // URL 暂不支持，使用演示数据
        setTimeout(() => {
          navigate('/analysis/demo');
        }, 1000);
        setProcessingInput(false);
        return;
      }

      // 开始轮询任务状态
      pollTaskStatus(
        response.task_id,
        (status) => {
          updateTaskProgress(taskId, status);
        }
      ).then((finalStatus) => {
        if (finalStatus.status === 'completed') {
          setTimeout(() => {
            navigate(`/analysis/${finalStatus.document_id}`);
          }, 1000);
        }
        setProcessingInput(false);
      });
    } catch (err) {
      updateTaskProgress(taskId, {
        task_id: taskId,
        document_id: '',
        status: 'failed',
        progress_percentage: 0,
        current_stage: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        completed_at: null,
        error_message: err instanceof Error ? err.message : '获取失败',
        evidence_items: [],
        processing_time_seconds: null,
        file_size_bytes: null,
      } as TaskStatusResponse);
      setProcessingInput(false);
    }
  };

  /**
   * 处理图谱搜索
   */
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchKeyword.trim()) return;
    navigate(`/graph?keyword=${encodeURIComponent(searchKeyword.trim())}`);
  };

  /**
   * 获取任务类型显示文本
   */
  const getTaskTypeText = (type: string): string => {
    switch (type) {
      case 'pdf_upload': return 'PDF 上传';
      case 'pmid_fetch': return 'PMID 分析';
      case 'doi_fetch': return 'DOI 分析';
      default: return '未知任务';
    }
  };

  /**
   * 获取状态图标
   */
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'processing':
        return <Loader2 className="spin" size={16} />;
      case 'completed':
        return <CheckCircle size={16} className="success" />;
      case 'failed':
        return <AlertCircle size={16} className="error" />;
      default:
        return <ClockIcon size={16} />;
    }
  };

  return (
    <div className="home-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-badge">
            <Sparkles size={14} />
            <span>多源文献智能解析系统</span>
          </div>
          <h1 className="hero-title">
            <span className="gradient-text">Multi-ACMG</span>
            <span>文献证据分析</span>
          </h1>
          <p className="hero-subtitle">
            智能解析医学文献，自动提取 ACMG 证据，构建知识图谱
            <br />
            支持语义章节对齐、三屏联动、精确证据定位
          </p>
        </div>
      </section>

      {/* Main Actions */}
      <section className="actions-section">
        {/* Upload/Input card */}
        <div className="action-card main-card">
          <div className="card-tabs">
            <button
              className={activeTab === 'upload' ? 'active' : ''}
              onClick={() => setActiveTab('upload')}
            >
              <Upload size={16} /> PDF 上传
            </button>
            <button
              className={activeTab === 'text' ? 'active' : ''}
              onClick={() => setActiveTab('text')}
            >
              <Link2 size={16} /> PMID/DOI/URL
            </button>
          </div>

          {activeTab === 'upload' ? (
            <div
              className={`upload-zone ${isDragging ? 'dragging' : ''} ${uploadError ? 'has-error' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {uploadError && (
                <div className={`upload-error ${uploadError.type}`}>
                  <AlertCircle size={20} />
                  <div className="error-content">
                    <strong>{uploadError.title}</strong>
                    <span>{uploadError.message}</span>
                    {uploadError.action && (
                      <span className="error-action">{uploadError.action}</span>
                    )}
                    {/* 重复文件错误：提供查看文档库选项 */}
                    {uploadError.title === '文件已上传过' && (
                      <div className="error-actions">
                        <button 
                          className="btn-view-library"
                          onClick={() => navigate('/library')}
                        >
                          查看文档库
                        </button>
                        <button 
                          className="btn-upload-other"
                          onClick={() => {
                            setUploadError(null);
                            handleSelectFile();
                          }}
                        >
                          上传其他文件
                        </button>
                      </div>
                    )}
                    <button 
                      className="btn-dismiss"
                      onClick={() => setUploadError(null)}
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              )}
              
              {/* 当前文件信息显示 */}
              {currentFile && !uploadError && (
                <div className="current-file-info">
                  <FileText size={16} />
                  <div className="file-details">
                    <span className="file-name">{currentFile.name}</span>
                    <span className="file-meta">{currentFile.size} · Hash: {currentFile.hash.slice(0, 16)}...</span>
                  </div>
                </div>
              )}
              <div className="upload-icon">
                <Upload size={48} />
              </div>
              <h3>拖拽 PDF 文件到此处</h3>
              <p>支持 PDF 格式，最大 50MB</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={(e) => {
                  if (e.target.files?.[0]) {
                    handleFileUpload(e.target.files[0]);
                    // 重置 input 以便可以再次选择同一文件
                    e.target.value = '';
                  }
                }}
              />
              <button 
                className="action-btn primary" 
                onClick={handleSelectFile}
                type="button"
              >
                选择文件 <ArrowRight size={16} />
              </button>
              
              {/* 调试模式：强制上传（绕过重复检测） */}
              {import.meta.env.DEV && (
                <div className="debug-options">
                  <label className="debug-upload-toggle warning">
                    <input
                      type="checkbox"
                      checked={forceUpload}
                      onChange={(e) => setForceUpload(e.target.checked)}
                    />
                    <span>⚠️ 强制上传（绕过重复检测）</span>
                  </label>
                  {currentFile && (
                    <div className="debug-hash-info">
                      <code>Hash: {currentFile.hash.slice(0, 24)}...</code>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <form onSubmit={handleTextSubmit} className="text-input-form">
              <div className="input-group">
                <FileText size={20} className="input-icon" />
                <input
                  type="text"
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="输入 PMID (如 12345678) 或 DOI/URL..."
                  disabled={processingInput}
                />
                {textInput && (
                  <span className={`input-type ${detectInputType(textInput)}`}>
                    {detectInputType(textInput).toUpperCase()}
                  </span>
                )}
              </div>
              <button
                type="submit"
                className="action-btn primary"
                disabled={!textInput.trim() || processingInput}
              >
                {processingInput ? (
                  <><Loader2 size={16} className="spin" /> 处理中...</>
                ) : (
                  <>开始分析 <ArrowRight size={16} /></>
                )}
              </button>
            </form>
          )}
        </div>

        {/* Graph search card */}
        <div className="action-card search-card">
          <div className="action-icon">
            <Network size={32} />
          </div>
          <h3>证据图谱</h3>
          <p>搜索基因、转录本、变异位点等</p>
          <form onSubmit={handleSearchSubmit}>
            <div className="search-input-group">
              <Search size={16} />
              <input
                type="text"
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                placeholder="输入关键词 (如 BRCA1, TRPV1)..."
              />
            </div>
            <button
              type="submit"
              className="action-btn"
              disabled={!searchKeyword.trim()}
            >
              搜索 <ArrowRight size={16} />
            </button>
          </form>
        </div>

        {/* Evidence demo card */}
        <div className="action-card demo-card" onClick={() => navigate('/evidence-demo')}>
          <div className="action-icon">
            <Microscope size={32} />
          </div>
          <h3>证据可视化演示</h3>
          <p>体验医学文献证据高亮与交互分析</p>
          <div className="demo-features">
            <span className="demo-tag">四窗格布局</span>
            <span className="demo-tag">实时高亮</span>
            <span className="demo-tag">双向交互</span>
          </div>
          <button className="action-btn primary">
            查看演示 <ArrowRight size={16} />
          </button>
        </div>
      </section>

      {/* Task status panel */}
      {queue.length > 0 && (
        <section className="task-panel">
          <div className="task-panel-header">
            <h3>任务状态</h3>
            {activeCount > 0 && (
              <span className="task-count">{activeCount} 个进行中</span>
            )}
          </div>
          <div className="task-list">
            {queue.map((task) => (
              <div key={task.id} className={`task-item ${task.status}`}>
                <div className="task-info">
                  {getStatusIcon(task.status)}
                  <div className="task-details">
                    <span className="task-type">{getTaskTypeText(task.type)}</span>
                    {task.description && (
                      <span className="task-desc">{task.description}</span>
                    )}
                  </div>
                </div>
                <div className="task-progress">
                  <div className="progress-bar">
                    <div 
                      className="progress-fill" 
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                  <div className="task-actions">
                    <span className="progress-text">{task.progress}%</span>
                    {task.documentId && (
                      <button 
                        className="btn-view"
                        onClick={() => navigate(`/analysis/${task.documentId}`)}
                      >
                        <Eye size={14} />
                      </button>
                    )}
                    <button 
                      className="btn-remove"
                      onClick={() => removeTask(task.id)}
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
                {task.currentStage && (
                  <span className="task-stage">{task.currentStage}</span>
                )}
                {task.error && <span className="error-text">{task.error}</span>}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Feature comparison */}
      <section className="features-section">
        <h2>核心功能</h2>
        <div className="features-grid">
          {features.map((feature, idx) => (
            <div key={idx} className="feature-card">
              <div className="feature-icon">{feature.icon}</div>
              <h4>{feature.title}</h4>
              <p className="feature-desc">{feature.desc}</p>
              <p className="feature-detail">{feature.detail}</p>
            </div>
          ))}
        </div>
        
        <button 
          className="more-features-btn"
          onClick={() => setShowMoreFeatures(!showMoreFeatures)}
        >
          {showMoreFeatures ? '收起' : '了解更多'}
          <ChevronRight size={16} className={showMoreFeatures ? 'rotate' : ''} />
        </button>
        
        {showMoreFeatures && (
          <div className="comparison-table">
            <table>
              <thead>
                <tr>
                  <th>问题</th>
                  <th>传统方案缺陷</th>
                  <th>本方案解决</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>内容长度差异</td>
                  <td>像素级滚动 → 严重错位</td>
                  <td>语义章节对齐 + 进度补偿</td>
                </tr>
                <tr>
                  <td>章节边界模糊</td>
                  <td>无法识别"当前章节"</td>
                  <td>Intersection Observer 精确识别</td>
                </tr>
                <tr>
                  <td>用户控制性差</td>
                  <td>被动同步，容易迷失</td>
                  <td>侧边栏导航 + 对齐按钮，用户主导</td>
                </tr>
                <tr>
                  <td>性能问题</td>
                  <td>高频滚动事件</td>
                  <td>防抖 + 节流 + 降级策略</td>
                </tr>
                <tr>
                  <td>小屏体验差</td>
                  <td>双栏挤压内容</td>
                  <td>响应式自动切换标签模式</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 代理连接测试 */}
      {import.meta.env.DEV && (
        <section className="proxy-test-section">
          <ProxyDiagnostic />
        </section>
      )}

      {/* Footer */}
      <footer className="home-footer">
        <p>Multi-ACMG 文献证据分析系统</p>
      </footer>
    </div>
  );
};

// 时钟图标组件
const ClockIcon: React.FC<{ size?: number }> = ({ size = 16 }) => (
  <svg 
    width={size} 
    height={size} 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

export default HomePage;
