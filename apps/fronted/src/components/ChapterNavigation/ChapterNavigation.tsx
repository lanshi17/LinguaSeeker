/**
 * Chapter Navigation Component
 * Displays document chapter structure, supports quick navigation and alignment
 */
import React, { useMemo } from 'react';
import { 
  ChevronRight,
  BookOpen,
  PanelLeftClose,
  PanelLeftOpen
} from 'lucide-react';
import type { Chapter } from '../../types';
import './ChapterNavigation.css';

interface ChapterNavigationProps {
  chapters: Chapter[];
  activeChapter: string | null;
  onChapterClick: (index: number) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

interface ChapterTreeItem extends Chapter {
  children: ChapterTreeItem[];
  mappedIndex?: number;
}

/**
 * Build chapter tree structure
 */
function buildChapterTree(chapters: Chapter[]): ChapterTreeItem[] {
  const root: ChapterTreeItem[] = [];
  const stack: ChapterTreeItem[] = [];
  
  chapters.forEach((chapter) => {
    const item: ChapterTreeItem = { ...chapter, children: [] };
    
    // Find parent node
    while (stack.length > 0 && stack[stack.length - 1].level >= chapter.level) {
      stack.pop();
    }
    
    if (stack.length === 0) {
      root.push(item);
    } else {
      stack[stack.length - 1].children.push(item);
    }
    
    stack.push(item);
  });
  
  return root;
}

/**
 * Recursively render chapter tree
 */
const ChapterTree: React.FC<{
  items: ChapterTreeItem[];
  activeId: string | null;
  onClick: (index: number) => void;
  level?: number;
}> = ({ items, activeId, onClick, level = 0 }) => {
  if (items.length === 0) return null;
  
  return (
    <ul className="chapter-tree" style={{ paddingLeft: level > 0 ? 16 : 0 }}>
      {items.map((item) => (
        <li key={item.id} className="chapter-tree-item">
          <button
            className={`chapter-nav-item ${activeId === item.id ? 'active' : ''}`}
            onClick={() => onClick(item.index)}
            style={{ paddingLeft: 12 + level * 8 }}
          >
            <ChevronRight 
              size={14} 
              className={`chapter-chevron ${item.children.length > 0 ? 'has-children' : ''}`}
            />
            <span className="chapter-title">{item.title}</span>
          </button>
          {item.children.length > 0 && (
            <ChapterTree
              items={item.children}
              activeId={activeId}
              onClick={onClick}
              level={level + 1}
            />
          )}
        </li>
      ))}
    </ul>
  );
};

export const ChapterNavigation: React.FC<ChapterNavigationProps> = ({
  chapters,
  activeChapter,
  onChapterClick,
  isCollapsed = false,
  onToggleCollapse,
}) => {
  // If collapsed, show simplified version
  if (isCollapsed) {
    return (
      <div className="chapter-navigation collapsed">
        <button 
          className="collapse-toggle-btn"
          onClick={onToggleCollapse}
          title="Expand chapter navigation"
        >
          <PanelLeftOpen size={20} />
        </button>
      </div>
    );
  }
  
  const chapterTree = useMemo(() => buildChapterTree(chapters), [chapters]);
  
  return (
    <div className="chapter-navigation">
      {/* Header */}
      <div className="chapter-nav-header">
        <div className="nav-title">
          <BookOpen size={18} />
          <span>Chapters</span>
        </div>
        <div className="nav-actions">
          <button
            className="collapse-btn"
            onClick={onToggleCollapse}
            title="Collapse chapter navigation"
          >
            <PanelLeftClose size={16} />
          </button>
        </div>
      </div>
      
      {/* Chapter tree */}
      <div className="chapter-tree-container">
        {chapterTree.length > 0 ? (
          <ChapterTree
            items={chapterTree}
            activeId={activeChapter}
            onClick={onChapterClick}
          />
        ) : (
          <div className="empty-chapters">
            <p>No chapter structure detected</p>
            <p className="empty-hint">Document will be auto-divided by paragraphs</p>
          </div>
        )}
      </div>
      
      {/* Footer stats */}
      <div className="chapter-stats">
        <div className="stat-item">
          <span className="stat-label">Total Sections</span>
          <span className="stat-value">{chapters.length}</span>
        </div>
      </div>
    </div>
  );
};
