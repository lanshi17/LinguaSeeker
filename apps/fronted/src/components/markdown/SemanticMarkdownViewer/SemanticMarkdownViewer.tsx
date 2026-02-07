/**
 * Semantic Markdown Viewer Component
 * Supports chapter recognition, evidence highlighting, Intersection Observer tracking, LaTeX formulas
 * Evidence highlighting is based on English (translated) content
 */
import React, { useMemo, useEffect, useCallback, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeRaw from 'rehype-raw';
import rehypeKatex from 'rehype-katex';
import type { Components } from 'react-markdown';
import type { Evidence, TextPosition, Chapter } from '../../../types';
import { EvidenceTypeColors, type EvidenceTypeValue } from '../../../types';
import 'github-markdown-css/github-markdown.css';
import 'katex/dist/katex.min.css';
import './SemanticMarkdownViewer.css';

interface SemanticMarkdownViewerProps {
  content: string;
  evidences: Evidence[];
  chapters: Chapter[];
  highlightedPosition: TextPosition | null;
  activeChapterId: string | null;
  showEvidenceHighlight: boolean;
  enabledEvidenceTypes?: string[];
  onElementClick?: (position: TextPosition) => void;
  onChapterVisible?: (chapterId: string) => void;
  onScroll?: () => void;
  containerRef?: (el: HTMLElement | null) => void;
}

/**
 * Find all matching positions, excluding math formula areas
 */
function findAllOccurrencesSafe(text: string, keyword: string): number[] {
  const positions: number[] = [];
  
  // First identify all math formula areas (inline $...$ and block $$...$$)
  const mathRanges: Array<{ start: number; end: number }> = [];
  
  // Match block math formulas $$...$$
  const blockMathRegex = /\$\$[\s\S]*?\$\$/g;
  let match: RegExpExecArray | null;
  while ((match = blockMathRegex.exec(text)) !== null) {
    mathRanges.push({ start: match.index, end: match.index + match[0].length });
  }
  
  // Match inline math formulas $...$ (excluding $$)
  const inlineMathRegex = /(?<!\$)\$(?!\$)[^\$]*?(?<!\$)\$(?!\$)/g;
  let inlineMatch: RegExpExecArray | null;
  while ((inlineMatch = inlineMathRegex.exec(text)) !== null) {
    // TypeScript type narrowing doesn't persist in while loops, use non-null assertion
    const m = inlineMatch!;
    // Check if overlapping with block formulas
    const isOverlapping = mathRanges.some(
      r => (m.index >= r.start && m.index < r.end) ||
           (m.index + m[0].length > r.start && m.index + m[0].length <= r.end)
    );
    if (!isOverlapping) {
      mathRanges.push({ start: m.index, end: m.index + m[0].length });
    }
  }
  
  // Find keyword positions, excluding math formula areas
  let pos = 0;
  while ((pos = text.indexOf(keyword, pos)) !== -1) {
    const matchEnd = pos + keyword.length;
    // Check if within math formula area
    const isInMath = mathRanges.some(
      r => (pos >= r.start && pos < r.end) || (matchEnd > r.start && matchEnd <= r.end)
    );
    
    if (!isInMath) {
      positions.push(pos);
    }
    pos += 1;
  }
  
  return positions;
}

/**
 * Custom image component with loading state
 */
const ImageComponent: React.FC<React.ImgHTMLAttributes<HTMLImageElement>> = (props) => {
  const [loaded, setLoaded] = React.useState(false);
  const [error, setError] = React.useState(false);

  return (
    <span className={`md-image-wrapper ${loaded ? 'loaded' : ''} ${error ? 'error' : ''}`}>
      {!loaded && !error && <span className="image-placeholder">Loading...</span>}
      {error && <span className="image-error">Failed to load image</span>}
      <img
        {...props}
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
        style={{ display: loaded ? 'block' : 'none' }}
      />
    </span>
  );
};

/**
 * Create chapter-aware heading component
 */
const createHeadingComponent = (
  chapters: Chapter[],
  onVisible: (id: string) => void,
  Tag: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6'
) => {
  return React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
    ({ children, ...props }, ref) => {
      const elementRef = useRef<HTMLHeadingElement>(null);
      
      // Merge ref
      useEffect(() => {
        if (typeof ref === 'function') {
          ref(elementRef.current);
        } else if (ref) {
          (ref as React.MutableRefObject<HTMLHeadingElement | null>).current = elementRef.current;
        }
      }, [ref]);
      
      // Find corresponding chapter
      const chapterTitle = typeof children === 'string' ? children : '';
      const chapter = chapters.find(c => c.title === chapterTitle && c.level === parseInt(Tag[1]));
      
      // Intersection Observer tracking
      useEffect(() => {
        if (!chapter || !elementRef.current) return;
        
        const observer = new IntersectionObserver(
          (entries) => {
            entries.forEach(entry => {
              if (entry.isIntersecting) {
                onVisible(chapter.id);
              }
            });
          },
          { rootMargin: '-10% 0px -70% 0px', threshold: 0 }
        );
        
        observer.observe(elementRef.current);
        return () => observer.disconnect();
      }, [chapter, onVisible]);
      
      const HeadingTag = Tag;
      
      if (!chapter) {
        return <HeadingTag ref={elementRef} {...props}>{children}</HeadingTag>;
      }
      
      return (
        <HeadingTag
          ref={elementRef}
          data-chapter-id={chapter.id}
          data-chapter-level={chapter.level}
          className={`chapter-heading chapter-level-${chapter.level}`}
          {...props}
        >
          {children}
        </HeadingTag>
      );
    }
  );
};

export const SemanticMarkdownViewer: React.FC<SemanticMarkdownViewerProps> = ({
  content,
  evidences,
  chapters,
  highlightedPosition,
  activeChapterId: _activeChapterId,
  showEvidenceHighlight,
  enabledEvidenceTypes,
  onElementClick,
  onChapterVisible,
  onScroll,
  containerRef,
}) => {
  const internalRef = useRef<HTMLDivElement>(null);
  
  // Merge external ref
  const setRef = useCallback((el: HTMLDivElement | null) => {
    internalRef.current = el;
    containerRef?.(el);
  }, [containerRef]);

  // Handle scroll event
  const handleScroll = useCallback(() => {
    onScroll?.();
  }, [onScroll]);

  // Preprocess content, add evidence highlighting (only when enabled)
  const processedContent = useMemo(() => {
    // If highlighting disabled or no types enabled, return original content
    if (!showEvidenceHighlight || !enabledEvidenceTypes || enabledEvidenceTypes.length === 0) {
      return content;
    }
    
    let result = content;
    const marks: Array<{
      start: number;
      end: number;
      evidenceId: string;
      positionId: string;
      evidenceType: EvidenceTypeValue;
    }> = [];

    // Collect highlight positions for each evidence (only enabled types)
    evidences.forEach((evidence) => {
      // Check if evidence type is in enabled list
      if (!enabledEvidenceTypes.includes(evidence.type)) {
        return;
      }
      
      // Use English keyword for highlighting (translated content)
      const keyword = evidence.keyword;
      if (!keyword) return;
      
      const occurrences = findAllOccurrencesSafe(result, keyword);
      
      occurrences.forEach((startPos, idx) => {
        marks.push({
          start: startPos,
          end: startPos + keyword.length,
          evidenceId: evidence.id,
          positionId: `${evidence.id}-${idx}`,
          evidenceType: evidence.type,
        });
      });
    });

    // Sort by position, replace from end to start to avoid offset issues
    marks.sort((a, b) => b.start - a.start);

    // Insert HTML marks
    marks.forEach((mark) => {
      const color = EvidenceTypeColors[mark.evidenceType];
      const before = result.slice(0, mark.start);
      const target = result.slice(mark.start, mark.end);
      const after = result.slice(mark.end);

      const markedHtml = `<mark 
        data-evidence-id="${mark.evidenceId}" 
        data-position-id="${mark.positionId}"
        data-evidence-type="${mark.evidenceType}"
        class="evidence-mark evidence-type-${mark.evidenceType}"
        style="background-color: ${color}35; border-bottom: 2px solid ${color};"
      >${target}</mark>`;

      result = before + markedHtml + after;
    });

    return result;
  }, [content, evidences, showEvidenceHighlight, enabledEvidenceTypes]);

  // Highlight currently selected evidence
  useEffect(() => {
    if (!internalRef.current || !highlightedPosition) return;

    // If highlighting disabled, skip
    if (!showEvidenceHighlight) return;

    // Delay execution, wait for content to render
    const timer = setTimeout(() => {
      const targetEl = internalRef.current?.querySelector(
        `[data-position-id="${highlightedPosition.id}"]`
      ) as HTMLElement;

      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        targetEl.classList.add('evidence-highlight-active');
        const highlightTimer = setTimeout(() => {
          targetEl.classList.remove('evidence-highlight-active');
        }, 2000);
        return () => clearTimeout(highlightTimer);
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [highlightedPosition, showEvidenceHighlight]);

  // Handle click event delegation
  const handleClick = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    const markEl = target.closest('.evidence-mark') as HTMLElement;
    
    if (markEl && onElementClick) {
      const positionId = markEl.getAttribute('data-position-id');
      const evidenceId = markEl.getAttribute('data-evidence-id');
      
      if (positionId && evidenceId) {
        const evidence = evidences.find((e) => e.id === evidenceId);
        const position = evidence?.positions.find((p) => p.id === positionId);
        if (position) {
          onElementClick(position);
        }
      }
    }
  }, [evidences, onElementClick]);

  // Custom component mapping
  const components: Components = useMemo(() => ({
    mark: ({ ...props }) => <mark {...props} />,
    img: ImageComponent,
    h1: createHeadingComponent(chapters, onChapterVisible || (() => {}), 'h1'),
    h2: createHeadingComponent(chapters, onChapterVisible || (() => {}), 'h2'),
    h3: createHeadingComponent(chapters, onChapterVisible || (() => {}), 'h3'),
    h4: createHeadingComponent(chapters, onChapterVisible || (() => {}), 'h4'),
    h5: createHeadingComponent(chapters, onChapterVisible || (() => {}), 'h5'),
    h6: createHeadingComponent(chapters, onChapterVisible || (() => {}), 'h6'),
  }), [chapters, onChapterVisible]);

  return (
    <div 
      ref={setRef}
      className="semantic-markdown-viewer markdown-body"
      onScroll={handleScroll}
      onClick={handleClick}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeRaw, rehypeKatex]}
        components={components}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}
