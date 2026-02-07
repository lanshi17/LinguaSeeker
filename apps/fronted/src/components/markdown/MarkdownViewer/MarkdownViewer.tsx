/**
 * Markdown 渲染组件
 * 支持证据标注、图片加载、滚动同步
 */
import React, { useMemo, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import type { Components } from 'react-markdown';
import type { Evidence, TextPosition } from '../../../types';
import { EvidenceTypeColors, type EvidenceTypeValue } from '../../../types';
import 'github-markdown-css/github-markdown.css';
import './MarkdownViewer.css';

interface MarkdownViewerProps {
  content: string;
  evidences: Evidence[];
  highlightedPosition: TextPosition | null;
  onElementClick?: (position: TextPosition) => void;
  panelRef?: React.RefObject<HTMLDivElement | null>;
  onScroll?: (ratio: number) => void;
}

/**
 * 查找所有匹配位置
 */
function findAllOccurrences(text: string, keyword: string): number[] {
  const positions: number[] = [];
  let pos = 0;
  while ((pos = text.indexOf(keyword, pos)) !== -1) {
    positions.push(pos);
    pos += 1;
  }
  return positions;
}

/**
 * 自定义图片组件 - 支持加载状态
 */
const ImageComponent: React.FC<React.ImgHTMLAttributes<HTMLImageElement>> = (props) => {
  const [loaded, setLoaded] = React.useState(false);
  const [error, setError] = React.useState(false);

  return (
    <span className={`md-image-wrapper ${loaded ? 'loaded' : ''} ${error ? 'error' : ''}`}>
      {!loaded && !error && <span className="image-placeholder">加载中...</span>}
      {error && <span className="image-error">图片加载失败</span>}
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
 * 自定义 mark 组件
 */
const MarkComponent: React.FC<React.HTMLAttributes<HTMLElement>> = (props) => {
  return <mark {...props}>{props.children}</mark>;
};

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({
  content,
  evidences,
  highlightedPosition,
  onElementClick,
  panelRef,
  onScroll,
}) => {
  // 处理滚动事件
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    if (!onScroll) return;
    const el = e.currentTarget;
    const maxScroll = el.scrollHeight - el.clientHeight;
    if (maxScroll > 0) {
      const ratio = el.scrollTop / maxScroll;
      onScroll(ratio);
    }
  }, [onScroll]);

  // 预处理内容，添加证据标注
  const processedContent = useMemo(() => {
    let result = content;
    const marks: Array<{
      start: number;
      end: number;
      evidenceId: string;
      positionId: string;
      evidenceType: EvidenceTypeValue;
    }> = [];

    // 为每个证据收集标注位置
    evidences.forEach((evidence) => {
      const keyword = evidence.keyword;
      const occurrences = findAllOccurrences(result, keyword);
      
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

    // 按位置排序，从后往前替换避免位置偏移
    marks.sort((a, b) => b.start - a.start);

    // 插入 HTML 标记
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
  }, [content, evidences]);

  // 高亮当前选中的证据
  useEffect(() => {
    if (!panelRef?.current || !highlightedPosition) return;

    const panel = panelRef.current;
    const targetEl = panel.querySelector(
      `[data-position-id="${highlightedPosition.id}"]`
    ) as HTMLElement;

    if (targetEl) {
      targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      targetEl.classList.add('evidence-highlight');
      const timer = setTimeout(() => {
        targetEl.classList.remove('evidence-highlight');
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [highlightedPosition, panelRef]);

  // 处理点击事件委托
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

  // 自定义组件映射
  const components: Components = useMemo(() => ({
    mark: MarkComponent,
    img: ImageComponent,
  }), []);

  return (
    <div 
      ref={panelRef}
      className="markdown-viewer markdown-body"
      onScroll={handleScroll}
      onClick={handleClick}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={components}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};
