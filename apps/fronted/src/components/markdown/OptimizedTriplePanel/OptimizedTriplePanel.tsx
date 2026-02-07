/**
 * Optimized Triple Panel Component
 * 
 * Features:
 * - Semantic chapter alignment
 * - Intersection Observer chapter tracking
 * - Debounced/throttled scroll sync
 * - Sidebar chapter navigation
 * - Responsive tab mode (auto-switch on small screens)
 * - Evidence highlighting based on English (translated) content
 */
import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useDocumentStore } from '../../../store/documentStore';
import { SemanticMarkdownViewer } from '../SemanticMarkdownViewer/SemanticMarkdownViewer';
import { ChapterNavigation } from '../ChapterNavigation/ChapterNavigation';
import { EvidencePanel } from '../../evidence/EvidencePanel/EvidencePanel';
import { PDFViewer } from '../PDFViewer/PDFViewer';
import { useChapters } from '../../../hooks/useChapters';
import { useScrollSync } from '../../../hooks/useScrollSync';
import { URLStateManager } from '../../../utils/helpers/urlState';
import type { DocumentData, Evidence } from '../../../types';
import { 
  FileText, 
  Languages, 
  List, 
  Share2,
  ChevronLeft,
  ChevronRight,
  Highlighter
} from 'lucide-react';
import './OptimizedTriplePanel.css';

interface OptimizedTriplePanelProps {
  document: DocumentData;
  onShare?: () => void;
}

type PanelTab = 'original' | 'translated' | 'evidence';
type ViewMode = 'split' | 'tabs';

export const OptimizedTriplePanel: React.FC<OptimizedTriplePanelProps> = ({
  document,
  onShare,
}) => {
  const {
    selectedEvidenceId,
    highlightedPosition,
    pdfCurrentPage,
    showEvidenceHighlight,
    enabledEvidenceTypes,
    selectEvidence,
    setPdfPage,
    toggleEvidenceHighlight,
  } = useDocumentStore();
  
  // Responsive view mode
  const [viewMode, setViewMode] = useState<ViewMode>('split');
  const [activeTab, setActiveTab] = useState<PanelTab>('translated');  // Default to translated (English)
  const [isNavCollapsed, setIsNavCollapsed] = useState(false);
  const [, setCurrentPanel] = useState<'original' | 'translated'>('translated');  // Track focus, value not displayed
  
  // Detect screen size changes
  useEffect(() => {
    const checkScreenSize = () => {
      setViewMode(window.innerWidth < 1024 ? 'tabs' : 'split');
    };
    
    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);
  
  // Chapter parsing
  const {
    originalChapters,
    translatedChapters,
    chapterMap,
    reverseChapterMap,
  } = useChapters({
    originalContent: document.originalMarkdown,
    translatedContent: document.translatedMarkdown,
  });
  
  // Scroll synchronization
  const {
    originalState,
    translatedState,
    setOriginalRef,
    setTranslatedRef,
    handleOriginalScroll,
    handleTranslatedScroll,
    syncToChapter,
    setChapterState,
    pauseSync,
    resumeSync,
  } = useScrollSync({
    originalChapters,
    translatedChapters,
    chapterMap,
    reverseChapterMap,
  });
  
  // Current active chapters
  const activeOriginalChapter = useMemo(() => {
    return originalChapters[originalState.chapterIndex]?.id || null;
  }, [originalChapters, originalState.chapterIndex]);
  
  const activeTranslatedChapter = useMemo(() => {
    return translatedChapters[translatedState.chapterIndex]?.id || null;
  }, [translatedChapters, translatedState.chapterIndex]);
  
  // Sync state to URL
  useEffect(() => {
    const params = URLStateManager.stateToParams(document.id, {
      activeEvidenceId: selectedEvidenceId,
      scrollRatio: 0,
      highlightedPosition,
      pdfPage: pdfCurrentPage,
    });
    URLStateManager.syncToURL(params);
  }, [document.id, selectedEvidenceId, highlightedPosition, pdfCurrentPage]);
  
  // Unified text search jump function - improved, more reliable positioning
  const scrollToKeyword = useCallback((
    panelSelector: string,
    keyword: string,
    fallbackChapterIndex: number,
    panel: 'original' | 'translated'
  ): Promise<boolean> => {
    const container = window.document.querySelector(panelSelector);
    if (!container || !keyword) return Promise.resolve(false);

    const containerEl = container as HTMLElement;
    
    // Wait for any pending rendering
    return new Promise<boolean>((resolve) => {
      requestAnimationFrame(() => {
        // Try exact match first, then partial match
        const keywordsToTry = [keyword];
        
        // Add partial keywords for fuzzy search (for long keywords)
        if (keyword.length > 10) {
          // Try first 10 chars and last 10 chars
          keywordsToTry.push(keyword.slice(0, 10));
          keywordsToTry.push(keyword.slice(-10));
        }
        if (keyword.length > 5) {
          keywordsToTry.push(keyword.slice(0, 5));
        }
        
        let foundNode: Text | null = null;
        let foundKeyword = '';
        
        for (const tryKeyword of keywordsToTry) {
          if (!tryKeyword || tryKeyword.length < 3) continue;
          
          // Find text nodes containing keyword
          const walker = window.document.createTreeWalker(
            container,
            NodeFilter.SHOW_TEXT
          );

          let node: Node | null;
          let bestNode: Text | null = null;
          let bestOffset = Infinity;
          
          // Iterate all text nodes to find best match
          while (node = walker.nextNode()) {
            const text = node.textContent || '';
            const index = text.indexOf(tryKeyword);
            
            if (index !== -1) {
              // Calculate approximate position in container
              const nodeRect = (node.parentElement as HTMLElement).getBoundingClientRect();
              const containerRect = containerEl.getBoundingClientRect();
              const relativeTop = nodeRect.top - containerRect.top + containerEl.scrollTop;
              
              // Prioritize nodes near viewport (near current scroll position)
              const offset = Math.abs(relativeTop - containerEl.scrollTop);
              
              if (!bestNode || offset < bestOffset) {
                bestNode = node as Text;
                bestOffset = offset;
              }
            }
          }
          
          if (bestNode) {
            foundNode = bestNode;
            foundKeyword = tryKeyword;
            break; // Found a match with this keyword
          }
        }

        if (foundNode) {
          // Create range and scroll into view
          const range = window.document.createRange();
          const text = foundNode.textContent || '';
          const keywordIndex = text.indexOf(foundKeyword);
          
          try {
            // Precisely position to keyword
            range.setStart(foundNode, keywordIndex);
            range.setEnd(foundNode, keywordIndex + foundKeyword.length);
            
            const rect = range.getBoundingClientRect();
            const containerRect = containerEl.getBoundingClientRect();
            
            // Calculate target scroll position (keyword slightly above center)
            const targetScrollTop = containerEl.scrollTop + rect.top - containerRect.top - (containerRect.height / 2) + 100;
            
            containerEl.scrollTo({
              top: Math.max(0, targetScrollTop),
              behavior: 'smooth'
            });
            
            // Add highlight effect
            const parentEl = foundNode.parentElement;
            if (parentEl) {
              parentEl.classList.add('evidence-jump-highlight');
              setTimeout(() => {
                parentEl.classList.remove('evidence-jump-highlight');
              }, 2000);
            }
            
            resolve(true);
          } catch (e) {
            console.warn('Range selection failed:', e);
            resolve(false);
          }
        } else {
          // Text search failed, fallback to chapter jump
          const chapters = panel === 'original' ? originalChapters : translatedChapters;
          const safeIndex = Math.min(fallbackChapterIndex, chapters.length - 1);
          if (safeIndex >= 0) {
            syncToChapter(safeIndex, panel);
          }
          resolve(false);
        }
      });
    }).then(result => result);
  }, [originalChapters, translatedChapters, syncToChapter]);

  // Handle evidence click - jump both panels simultaneously, ensure consistent positioning
  const handleEvidenceClick = useCallback(async (evidence: Evidence) => {
    // Get bilingual position info
    const bilingualPos = evidence.bilingualPositions?.[0];
    const originalPos = bilingualPos?.original ?? evidence.positions[0];
    const translatedPos = bilingualPos?.translated;
    
    if (!originalPos) return;

    // Pause chapter sync to avoid jump conflicts
    pauseSync();
    selectEvidence(evidence.id, originalPos);

    // On small screens, only handle the active panel
    if (viewMode === 'tabs') {
      const targetPanel = activeTab === 'translated' ? 'translated' : 'original';
      const targetPos = targetPanel === 'translated' && translatedPos ? translatedPos : originalPos;
      const targetKeyword = targetPanel === 'translated' && evidence.originalKeyword 
        ? evidence.keyword  // Translated panel uses translated keyword
        : evidence.originalKeyword || evidence.keyword;  // Original panel prefers original keyword
      
      setCurrentPanel(targetPanel);
      await new Promise(resolve => setTimeout(resolve, 150));
      await scrollToKeyword(
        `.panel-${targetPanel} .semantic-markdown-viewer, .tab-content .semantic-markdown-viewer`,
        targetKeyword,
        targetPos.paragraphIndex,
        targetPanel
      );
      // Sync outline state - outline shows translated chapters only
      const outlineIndex = targetPanel === 'translated' 
        ? targetPos.paragraphIndex 
        : (reverseChapterMap.get(targetPos.paragraphIndex) ?? targetPos.paragraphIndex);
      setChapterState(outlineIndex, 'translated');
      // Delay resume sync
      setTimeout(() => resumeSync(), 800);
      return;
    }

    // In split view mode, jump both panels simultaneously
    await new Promise(resolve => setTimeout(resolve, 50));
    
    // Original panel jump - use original keyword and position
    const originalKeyword = evidence.originalKeyword || evidence.keyword;
    const originalPromise = scrollToKeyword(
      '.panel-original .semantic-markdown-viewer',
      originalKeyword,
      originalPos.paragraphIndex,
      'original'
    );

    // Translated panel jump - use translated keyword and position (if available)
    const translatedPromise = new Promise<void>(resolve => {
      setTimeout(async () => {
        // 优先使用双语定位中的译文位置
        if (translatedPos) {
          await scrollToKeyword(
            '.panel-translated .semantic-markdown-viewer',
            evidence.keyword,  // 译文关键词
            translatedPos.paragraphIndex,
            'translated'
          );
        } else {
          // Fallback to chapter mapping
          const mappedIndex = chapterMap.get(originalPos.paragraphIndex);
          const translatedIndex = mappedIndex !== undefined ? mappedIndex : originalPos.paragraphIndex;
          await scrollToKeyword(
            '.panel-translated .semantic-markdown-viewer',
            evidence.keyword,
            translatedIndex,
            'translated'
          );
        }
        resolve();
      }, 50);
    });

    await Promise.all([originalPromise, translatedPromise]);
    
    // Update current panel state to original (default), ensure outline displays correctly
    setCurrentPanel('original');
    
    // Sync outline state to translated chapter (outline shows English only)
    const translatedOutlineIndex = translatedPos 
      ? translatedPos.paragraphIndex 
      : (chapterMap.get(originalPos.paragraphIndex) ?? originalPos.paragraphIndex);
    setChapterState(translatedOutlineIndex, 'translated');

    // Delay resume sync
    setTimeout(() => {
      resumeSync();
    }, 800);
  }, [selectEvidence, scrollToKeyword, viewMode, activeTab, chapterMap, pauseSync, resumeSync, setChapterState]);
  
  // Handle chapter navigation click - navigate English translation and sync original
  const handleChapterClick = useCallback((index: number) => {
    // First, scroll the translated panel to the clicked chapter
    syncToChapter(index, 'translated');
    
    // Then sync the original panel to the corresponding mapped chapter
    // Use reverseChapterMap: translated index -> original index
    const mappedOriginalIndex = reverseChapterMap.get(index);
    if (mappedOriginalIndex !== undefined) {
      syncToChapter(mappedOriginalIndex, 'original');
    }
  }, [syncToChapter, reverseChapterMap]);
  
  // Handle chapter visibility change (from Intersection Observer)
  const handleChapterVisible = useCallback(() => {
    // Chapter visibility is tracked automatically via scroll sync
  }, []);
  
  // Check if has PDF
  const hasPDF = document.pdfUrl || document.id === 'demo';
  
  // Split view rendering
  const renderSplitView = () => (
    <div className="split-view">
      {/* Left panel - Original */}
      <div className="split-panel panel-original">
        <PanelHeader 
          icon={<FileText size={16} />}
          title="Original"
          badge={hasPDF ? 'PDF' : 'Markdown'}
          onFocus={() => setCurrentPanel('original')}
        />
        <div className="panel-content">
          {hasPDF && document.pdfUrl ? (
            <PDFViewer
              pdfUrl={document.pdfUrl}
              evidences={document.evidences}
              highlightedPosition={highlightedPosition}
              currentPage={pdfCurrentPage}
              onPageChange={setPdfPage}
            />
          ) : (
            <SemanticMarkdownViewer
              content={document.originalMarkdown}
              evidences={document.evidences}
              chapters={originalChapters}
              highlightedPosition={highlightedPosition}
              activeChapterId={activeOriginalChapter}
              showEvidenceHighlight={showEvidenceHighlight}
              enabledEvidenceTypes={enabledEvidenceTypes}
              onChapterVisible={handleChapterVisible}
              onScroll={handleOriginalScroll}
              containerRef={setOriginalRef}
            />
          )}
        </div>
      </div>
      
      {/* Middle panel - Translated (English) */}
      <div className="split-panel panel-translated">
        <PanelHeader 
          icon={<Languages size={16} />}
          title="English"
          badge="Markdown"
          onFocus={() => setCurrentPanel('translated')}
        />
        <div className="panel-content">
          <SemanticMarkdownViewer
            content={document.translatedMarkdown}
            evidences={document.evidences}
            chapters={translatedChapters}
            highlightedPosition={highlightedPosition}
            activeChapterId={activeTranslatedChapter}
            showEvidenceHighlight={showEvidenceHighlight}
            enabledEvidenceTypes={enabledEvidenceTypes}
            onChapterVisible={handleChapterVisible}
            onScroll={handleTranslatedScroll}
            containerRef={setTranslatedRef}
          />
        </div>
      </div>
      
      {/* Right panel - Evidence */}
      <div className="split-panel panel-evidence">
        <PanelHeader 
          icon={<List size={16} />}
          title="Evidence"
          badge={`${document.evidences.length}`}
        />
        <div className="panel-content">
          <EvidencePanel
            evidences={document.evidences}
            activeEvidenceId={selectedEvidenceId}
            onEvidenceClick={handleEvidenceClick}
            docTitle={document.title}
          />
        </div>
      </div>
    </div>
  );
  
  // Tab view rendering (small screens)
  const renderTabView = () => (
    <div className="tab-view">
      <div className="tab-bar">
        <button
          className={`tab-btn ${activeTab === 'original' ? 'active' : ''}`}
          onClick={() => setActiveTab('original')}
        >
          <FileText size={16} /> Original
        </button>
        <button
          className={`tab-btn ${activeTab === 'translated' ? 'active' : ''}`}
          onClick={() => setActiveTab('translated')}
        >
          <Languages size={16} /> English
        </button>
        <button
          className={`tab-btn ${activeTab === 'evidence' ? 'active' : ''}`}
          onClick={() => setActiveTab('evidence')}
        >
          <List size={16} /> Evidence
          <span className="tab-badge">{document.evidences.length}</span>
        </button>
      </div>
      
      <div className="tab-content">
        {activeTab === 'original' && (
          hasPDF && document.pdfUrl ? (
            <PDFViewer
              pdfUrl={document.pdfUrl}
              evidences={document.evidences}
              highlightedPosition={highlightedPosition}
              currentPage={pdfCurrentPage}
              onPageChange={setPdfPage}
            />
          ) : (
            <SemanticMarkdownViewer
              content={document.originalMarkdown}
              evidences={document.evidences}
              chapters={originalChapters}
              highlightedPosition={highlightedPosition}
              activeChapterId={activeOriginalChapter}
              showEvidenceHighlight={showEvidenceHighlight}
              enabledEvidenceTypes={enabledEvidenceTypes}
              onChapterVisible={handleChapterVisible}
              onScroll={handleOriginalScroll}
              containerRef={setOriginalRef}
            />
          )
        )}
        {activeTab === 'translated' && (
          <SemanticMarkdownViewer
            content={document.translatedMarkdown}
            evidences={document.evidences}
            chapters={translatedChapters}
            highlightedPosition={highlightedPosition}
            activeChapterId={activeTranslatedChapter}
            showEvidenceHighlight={showEvidenceHighlight}
            enabledEvidenceTypes={enabledEvidenceTypes}
            onChapterVisible={handleChapterVisible}
            onScroll={handleTranslatedScroll}
            containerRef={setTranslatedRef}
          />
        )}
        {activeTab === 'evidence' && (
          <EvidencePanel
            evidences={document.evidences}
            activeEvidenceId={selectedEvidenceId}
            onEvidenceClick={handleEvidenceClick}
            docTitle={document.title}
          />
        )}
      </div>
    </div>
  );
  
  return (
    <div className="optimized-triple-panel">
      {/* Top toolbar */}
      <div className="panel-toolbar">
        <div className="toolbar-left">
          <h2 className="doc-title">{document.title}</h2>
          <span className="doc-meta">
            {document.doi || 'Research Article'}
          </span>
        </div>
        <div className="toolbar-right">
          <button
            className={`toolbar-btn ${showEvidenceHighlight ? 'active' : ''}`}
            onClick={toggleEvidenceHighlight}
            title={showEvidenceHighlight ? 'Disable highlighting' : 'Enable highlighting'}
          >
            <Highlighter size={16} />
            {showEvidenceHighlight ? 'On' : 'Off'}
          </button>
          {viewMode === 'split' && (
            <button
              className="toolbar-btn"
              onClick={() => setIsNavCollapsed(!isNavCollapsed)}
              title={isNavCollapsed ? 'Expand navigation' : 'Collapse navigation'}
            >
              {isNavCollapsed ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
              Chapters
            </button>
          )}
          {onShare && (
            <button className="toolbar-btn primary" onClick={onShare}>
              <Share2 size={16} />
              Share
            </button>
          )}
        </div>
      </div>
      
      {/* Main content area */}
      <div className="panel-main">
        {/* Chapter navigation - English translation only (split mode only) */}
        {viewMode === 'split' && (
          <div className={`chapter-sidebar left ${isNavCollapsed ? 'collapsed' : ''}`}>
            <ChapterNavigation
              chapters={translatedChapters}
              activeChapter={activeTranslatedChapter}
              onChapterClick={handleChapterClick}
              isCollapsed={isNavCollapsed}
              onToggleCollapse={() => setIsNavCollapsed(!isNavCollapsed)}
            />
          </div>
        )}
        
        {viewMode === 'split' ? renderSplitView() : renderTabView()}
      </div>
    </div>
  );
};

/**
 * Panel header sub-component
 */
interface PanelHeaderProps {
  icon: React.ReactNode;
  title: string;
  badge?: string;
  onFocus?: () => void;
}

const PanelHeader: React.FC<PanelHeaderProps> = ({ icon, title, badge, onFocus }) => (
  <div className="split-panel-header" onClick={onFocus}>
    <div className="header-left">
      {icon}
      <span className="header-title">{title}</span>
    </div>
    {badge && <span className="header-badge">{badge}</span>}
  </div>
);
