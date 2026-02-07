/**
 * 医学证据可视化查看器
 * 四窗格布局：导航/大纲 | 原文 | 处理后原文 | 证据栏
 */
import React, { useState, useEffect, useRef } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

// DOMPurify sanitize helper
const sanitize = (html: string): string => {
  return DOMPurify.sanitize(html);
};
import { 
  FileText, 
  List, 
  Search, 
  Image as ImageIcon,
  ChevronDown,
  Bookmark
} from 'lucide-react';
import type { 
  EvidenceItem, 
  EvidenceAnalysis, 
  EvidencePurpose,
  EvidenceGroup 
} from '../../../types/evidence';
import { PURPOSE_LABELS, PURPOSE_COLORS } from '../../../types/evidence';
import './EvidenceViewer.css';

interface EvidenceViewerProps {
  basePath: string;
  documentId: string;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ 
  basePath, 
  documentId 
}) => {
  // 数据状态
  const [evidenceData, setEvidenceData] = useState<EvidenceAnalysis | null>(null);
  const [originalMd, setOriginalMd] = useState<string>('');
  const [processedMd, setProcessedMd] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 交互状态
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);
  const [outlineItems, setOutlineItems] = useState<{level: number; text: string; id: string}[]>([]);
  
  // Refs
  const processedRef = useRef<HTMLDivElement>(null);
  const evidenceListRef = useRef<HTMLDivElement>(null);

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const path = `${basePath}/${documentId}`;
        
        // 并行加载所有文件
        const [evidenceRes, originalRes, processedRes] = await Promise.all([
          fetch(`${path}/ps3_evidence.json`),
          fetch(`${path}/original_format.md`),
          fetch(`${path}/en_format.md`),
        ]);
        
        if (!evidenceRes.ok) throw new Error('Failed to load evidence data');
        if (!originalRes.ok) throw new Error('Failed to load original markdown');
        if (!processedRes.ok) throw new Error('Failed to load processed markdown');
        
        const evidence: EvidenceAnalysis = await evidenceRes.json();
        const original = await originalRes.text();
        const processed = await processedRes.text();
        
        setEvidenceData(evidence);
        setOriginalMd(original);
        setProcessedMd(processed);
        
        // 解析大纲
        parseOutline(processed);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, [basePath, documentId]);

  // 解析Markdown大纲
  const parseOutline = (markdown: string) => {
    const lines = markdown.split('\n');
    const items: {level: number; text: string; id: string}[] = [];
    
    lines.forEach((line, index) => {
      const match = line.match(/^(#{1,6})\s+(.+)$/);
      if (match) {
        const level = match[1].length;
        const text = match[2].trim();
        items.push({ level, text, id: `heading-${index}` });
      }
    });
    
    setOutlineItems(items);
  };

  // 处理高亮（在DOM渲染后执行）
  useEffect(() => {
    if (!processedRef.current || !evidenceData) return;
    
    const container = processedRef.current;
    const textNodes: Text[] = [];
    
    // 收集所有文本节点
    const walk = (node: Node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        textNodes.push(node as Text);
      } else {
        node.childNodes.forEach(walk);
      }
    };
    walk(container);
    
    // 获取完整文本内容用于定位（调试用）
    // const fullText = textNodes.map(n => n.textContent).join('');
    
    // 处理每个文本证据
    evidenceData.evidence_items
      .filter(item => item.type === 'text' && item.locator.char_start != null)
      .forEach(evidence => {
        const { char_start, char_end } = evidence.locator;
        if (char_start == null || char_end == null) return;
        
        // 查找包含该范围的文本节点
        let currentPos = 0;
        for (const textNode of textNodes) {
          const nodeLength = textNode.textContent?.length || 0;
          const nodeStart = currentPos;
          const nodeEnd = currentPos + nodeLength;
          
          // 检查是否有重叠
          if (char_start < nodeEnd && char_end > nodeStart) {
            const startOffset = Math.max(0, char_start - nodeStart);
            const endOffset = Math.min(nodeLength, char_end - nodeStart);
            
            try {
              const range = document.createRange();
              range.setStart(textNode, startOffset);
              range.setEnd(textNode, endOffset);
              
              const span = document.createElement('span');
              span.className = `evidence-highlight evidence-purpose-${evidence.purpose}`;
              span.dataset.evidenceId = evidence.id;
              span.style.backgroundColor = `${PURPOSE_COLORS[evidence.purpose]}30`;
              span.style.borderBottom = `2px solid ${PURPOSE_COLORS[evidence.purpose]}`;
              span.style.cursor = 'pointer';
              span.title = `${evidence.id}: ${PURPOSE_LABELS[evidence.purpose]}`;
              
              // 点击事件
              span.addEventListener('click', () => {
                setSelectedEvidence(evidence.id);
                scrollToEvidence(evidence.id);
              });
              
              range.surroundContents(span);
            } catch (e) {
              // 跨节点范围处理失败，跳过
              console.warn(`Failed to highlight ${evidence.id}:`, e);
            }
            break; // 只高亮第一个匹配的节点
          }
          
          currentPos += nodeLength;
        }
      });
    
    // 处理图片证据
    evidenceData.evidence_items
      .filter(item => item.type === 'image')
      .forEach(evidence => {
        const images = container.querySelectorAll('img');
        images.forEach((img) => {
          const alt = img.getAttribute('alt') || '';
          if (evidence.image_ref && alt.toLowerCase().includes(evidence.image_ref.toLowerCase())) {
            img.classList.add('evidence-image');
            img.dataset.evidenceId = evidence.id;
            img.style.border = `3px solid ${PURPOSE_COLORS[evidence.purpose]}`;
            img.style.borderRadius = '4px';
            
            img.addEventListener('click', () => {
              setSelectedEvidence(evidence.id);
              scrollToEvidence(evidence.id);
            });
          }
        });
      });
  }, [evidenceData, processedMd]);

  // 滚动到证据
  const scrollToEvidence = (evidenceId: string) => {
    const element = processedRef.current?.querySelector(`[data-evidence-id="${evidenceId}"]`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      element.classList.add('evidence-flash');
      setTimeout(() => element.classList.remove('evidence-flash'), 1500);
    }
  };

  // 点击证据项
  const handleEvidenceClick = (evidence: EvidenceItem) => {
    setSelectedEvidence(evidence.id);
    scrollToEvidence(evidence.id);
  };

  // 按purpose分组证据
  const groupedEvidence: EvidenceGroup[] = evidenceData 
    ? (Object.keys(PURPOSE_LABELS) as EvidencePurpose[])
        .map(purpose => ({
          purpose,
          label: PURPOSE_LABELS[purpose],
          items: evidenceData.evidence_items.filter(e => e.purpose === purpose)
        }))
        .filter(g => g.items.length > 0)
    : [];

  if (loading) {
    return (
      <div className="evidence-viewer-loading">
        <div className="spinner" />
        <span>加载医学证据分析...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="evidence-viewer-error">
        <p>加载失败: {error}</p>
      </div>
    );
  }

  return (
    <div className="evidence-viewer">
      {/* 左一: 导航/大纲 */}
      <aside className="panel panel-outline">
        <div className="panel-header">
          <List size={16} />
          <span>文档大纲</span>
        </div>
        <div className="outline-content">
          {outlineItems.map((item, index) => (
            <div 
              key={index}
              className={`outline-item level-${item.level}`}
              style={{ paddingLeft: `${(item.level - 1) * 16}px` }}
            >
              {item.text}
            </div>
          ))}
        </div>
      </aside>

      {/* 左二: 原文 */}
      <aside className="panel panel-original">
        <div className="panel-header">
          <FileText size={16} />
          <span>原始文献</span>
        </div>
        <div 
          className="markdown-content"
          dangerouslySetInnerHTML={{ 
            __html: sanitize(marked.parse(originalMd, { gfm: true, breaks: true }) as string) 
          }}
        />
      </aside>

      {/* 右二: 处理后原文（带高亮） */}
      <main className="panel panel-processed">
        <div className="panel-header">
          <Search size={16} />
          <span>分析视图</span>
          <div className="highlight-legend">
            {Object.entries(PURPOSE_LABELS).map(([key, label]) => (
              <span 
                key={key}
                className="legend-item"
                style={{ 
                  backgroundColor: `${PURPOSE_COLORS[key as EvidencePurpose]}30`,
                  borderColor: PURPOSE_COLORS[key as EvidencePurpose]
                }}
              >
                {label}
              </span>
            ))}
          </div>
        </div>
        <div 
          ref={processedRef}
          className="markdown-content processed"
          dangerouslySetInnerHTML={{ __html: processedMd ? DOMPurify.sanitize(marked.parse(processedMd, { gfm: true, breaks: true }) as string, { USE_PROFILES: { html: true } }) : '' }}
        />
      </main>

      {/* 右一: 证据栏 */}
      <aside className="panel panel-evidence" ref={evidenceListRef}>
        <div className="panel-header">
          <Bookmark size={16} />
          <span>证据列表</span>
        </div>
        <div className="evidence-content">
          {groupedEvidence.map(group => (
            <div key={group.purpose} className="evidence-group">
              <div 
                className="group-header"
                style={{ color: PURPOSE_COLORS[group.purpose] }}
              >
                <ChevronDown size={14} />
                <span>{group.label}</span>
                <span className="count">({group.items.length})</span>
              </div>
              <div className="group-items">
                {group.items.map(evidence => (
                  <div
                    key={evidence.id}
                    className={`evidence-card ${selectedEvidence === evidence.id ? 'selected' : ''}`}
                    onClick={() => handleEvidenceClick(evidence)}
                    style={{
                      borderLeft: `3px solid ${PURPOSE_COLORS[evidence.purpose]}`
                    }}
                  >
                    <div className="evidence-header">
                      <span className="evidence-id">{evidence.id}</span>
                      {evidence.type === 'image' ? (
                        <ImageIcon size={12} />
                      ) : (
                        <FileText size={12} />
                      )}
                    </div>
                    {evidence.quote && (
                      <p className="evidence-quote">
                        {evidence.quote.substring(0, 100)}
                        {evidence.quote.length > 100 && '...'}
                      </p>
                    )}
                    {evidence.keywords?.tex_wrapped && (
                      <div className="evidence-keywords">
                        {evidence.keywords.tex_wrapped.map((kw, i) => (
                          <code key={i} className="keyword-tag">{kw}</code>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
};

export default EvidenceViewer;
