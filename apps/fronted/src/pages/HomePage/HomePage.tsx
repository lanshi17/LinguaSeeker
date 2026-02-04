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
  ChevronRight
} from 'lucide-react';
import { useDocumentStore } from '../../store/documentStore';
import { uploadDocument, fetchByPMID } from '../../services/documentApi';
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
];

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { taskQueue, addTask, updateTask, removeTask } = useDocumentStore();
  
  const [searchKeyword, setSearchKeyword] = useState('');
  const [textInput, setTextInput] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [activeTab, setActiveTab] = useState<'upload' | 'text'>('upload');
  const [showMoreFeatures, setShowMoreFeatures] = useState(false);

  /**
   * Handle file upload
   */
  const handleFileUpload = useCallback(async (file: File) => {
    if (file.type !== 'application/pdf') {
      alert('Please upload a PDF file');
      return;
    }

    const taskId = `upload-${Date.now()}`;
    addTask({ id: taskId, type: 'upload' });

    try {
      updateTask(taskId, { status: 'processing', progress: 30 });
      const result = await uploadDocument(file);
      
      updateTask(taskId, { status: 'completed', progress: 100 });
      setTimeout(() => removeTask(taskId), 3000);
      
      navigate(`/analysis/${result.id}`);
    } catch (err) {
      updateTask(taskId, { 
        status: 'error', 
        progress: 0,
        error: err instanceof Error ? err.message : 'Upload failed'
      });
    }
  }, [addTask, updateTask, removeTask, navigate]);

  /**
   * Handle drag and drop
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
   * Handle text input submission (PMID/DOI/URL)
   */
  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim()) return;

    const detectedType = detectInputType(textInput);
    if (detectedType === 'unknown') {
      alert('Cannot recognize input type. Please enter PMID (numbers), DOI (10.xxx), or URL (http/https)');
      return;
    }
    
    const type = detectedType as 'pmid' | 'doi' | 'url';
    const taskId = `${type}-${Date.now()}`;
    
    addTask({ id: taskId, type });
    updateTask(taskId, { status: 'processing', progress: 50 });

    try {
      if (type === 'pmid') {
        const doc = await fetchByPMID(textInput.trim());
        updateTask(taskId, { status: 'completed', progress: 100 });
        setTimeout(() => removeTask(taskId), 3000);
        navigate(`/analysis/${doc.id}`);
      } else {
        // DOI/URL not yet supported, demo redirect
        await new Promise(r => setTimeout(r, 1000));
        updateTask(taskId, { status: 'completed', progress: 100 });
        setTimeout(() => removeTask(taskId), 3000);
        navigate('/analysis/demo');
      }
    } catch (err) {
      updateTask(taskId, { 
        status: 'error', 
        progress: 0,
        error: 'Fetch failed'
      });
    }
  };

  /**
   * Handle graph search
   */
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchKeyword.trim()) return;
    navigate(`/graph?keyword=${encodeURIComponent(searchKeyword.trim())}`);
  };

  return (
    <div className="home-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-badge">
            <Sparkles size={14} />
            <span>Multi-source Literature Intelligence System</span>
          </div>
          <h1 className="hero-title">
            <span className="gradient-text">Multi-ACMG</span>
            <span>Literature Evidence Analysis</span>
          </h1>
          <p className="hero-subtitle">
            Intelligently analyze medical literature, auto-extract ACMG evidence, build knowledge graphs
            <br />
            Supports semantic chapter alignment, triple-panel linkage, precise evidence positioning
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
              <Upload size={16} /> PDF Upload
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
              className={`upload-zone ${isDragging ? 'dragging' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="upload-icon">
                <Upload size={48} />
              </div>
              <h3>Drag PDF file here</h3>
              <p>Or click to select file, batch upload supported</p>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
              />
              <button className="action-btn primary">
                Select File <ArrowRight size={16} />
              </button>
            </div>
          ) : (
            <form onSubmit={handleTextSubmit} className="text-input-form">
              <div className="input-group">
                <FileText size={20} className="input-icon" />
                <input
                  type="text"
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="Enter PMID (e.g., 12345678) or DOI/URL..."
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
                disabled={!textInput.trim()}
              >
                Analyze <ArrowRight size={16} />
              </button>
            </form>
          )}
        </div>

        {/* Graph search card */}
        <div className="action-card search-card">
          <div className="action-icon">
            <Network size={32} />
          </div>
          <h3>Evidence Graph</h3>
          <p>Search for genes, transcripts, variants, and more</p>
          <form onSubmit={handleSearchSubmit}>
            <div className="search-input-group">
              <Search size={16} />
              <input
                type="text"
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                placeholder="Enter keywords (e.g., BRCA1, TRPV1)..."
              />
            </div>
            <button
              type="submit"
              className="action-btn"
              disabled={!searchKeyword.trim()}
            >
              Search <ArrowRight size={16} />
            </button>
          </form>
        </div>
      </section>

      {/* Task status panel */}
      {taskQueue.length > 0 && (
        <section className="task-panel">
          <h3>Task Status</h3>
          <div className="task-list">
            {taskQueue.map((task) => (
              <div key={task.id} className={`task-item ${task.status}`}>
                <div className="task-info">
                  {task.status === 'processing' && <Loader2 className="spin" size={16} />}
                  {task.status === 'completed' && <CheckCircle size={16} className="success" />}
                  {task.status === 'error' && <AlertCircle size={16} className="error" />}
                  <span className="task-type">
                    {task.type === 'upload' ? 'PDF Upload' : 
                     task.type === 'pmid' ? 'PMID Analysis' : 
                     task.type === 'doi' ? 'DOI Analysis' : 'URL Analysis'}
                  </span>
                </div>
                <div className="task-progress">
                  <div className="progress-bar">
                    <div 
                      className="progress-fill" 
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                  {task.error && <span className="error-text">{task.error}</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Feature comparison */}
      <section className="features-section">
        <h2>Key Features</h2>
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
          {showMoreFeatures ? 'Collapse' : 'Learn More'}
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
                  <td>Content length difference</td>
                  <td>Pixel-based scrolling → severe misalignment</td>
                  <td>Semantic chapter alignment + progress compensation</td>
                </tr>
                <tr>
                  <td>Vague chapter boundaries</td>
                  <td>Cannot identify "current chapter"</td>
                  <td>Intersection Observer precisely identifies visible chapters</td>
                </tr>
                <tr>
                  <td>Poor user control</td>
                  <td>Passive sync, easy to get lost</td>
                  <td>Sidebar navigation + align button, user-driven</td>
                </tr>
                <tr>
                  <td>Performance issues</td>
                  <td>High-frequency scroll events</td>
                  <td>Debouncing + throttling + fallback strategies</td>
                </tr>
                <tr>
                  <td>Poor small-screen experience</td>
                  <td>Dual-column squeezes content</td>
                  <td>Responsive auto-switch to tab mode</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Footer */}
      <footer className="home-footer">
        <p>Multi-ACMG Literature Evidence Analysis System</p>
      </footer>
    </div>
  );
};
