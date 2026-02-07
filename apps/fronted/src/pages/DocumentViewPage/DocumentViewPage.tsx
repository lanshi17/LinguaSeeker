/**
 * Document View Page
 * 动态加载和显示文献结构与内容
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Loader2, 
  AlertCircle, 
  ArrowLeft, 
  FileText, 
  Calendar, 
  User, 
  Tag,
  ChevronRight,
  ChevronDown,
  BookOpen,
  List,
  Grid3X3
} from 'lucide-react';
import { getDocument, APIError } from '../../services/api';
import type { DocumentParseResult, DocumentSection, EvidenceItemSummary } from '../../types';
import './DocumentViewPage.css';

/**
 * 文档数据类型
 */
interface DocumentData extends DocumentParseResult {
  isLoading?: boolean;
  error?: string;
}

/**
 * 章节项组件
 */
const SectionItem: React.FC<{
  section: DocumentSection;
  isActive: boolean;
  onClick: () => void;
  isExpanded: boolean;
}> = ({ section, isActive, onClick, isExpanded }) => {
  const getSectionIcon = (type: string) => {
    switch (type) {
      case 'title': return <BookOpen size={14} />;
      case 'abstract': return <FileText size={14} />;
      case 'background': return <List size={14} />;
      case 'methods': return <Grid3X3 size={14} />;
      case 'results': return <Tag size={14} />;
      case 'conclusion': return <ChevronRight size={14} />;
      default: return <ChevronRight size={14} />;
    }
  };

  return (
    <button
      className={`section-nav-item ${isActive ? 'active' : ''} level-${section.level}`}
      onClick={onClick}
    >
      <span className="section-icon">{getSectionIcon(section.type)}</span>
      <span className="section-title">{section.title}</span>
      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
    </button>
  );
};

/**
 * 证据项组件
 */
const EvidenceCard: React.FC<{ evidence: EvidenceItemSummary }> = ({ evidence }) => (
  <div className={`evidence-card ${evidence.review_required ? 'review-required' : ''}`}>
    <div className="evidence-card-header">
      <span className="evidence-code-badge">{evidence.acmg_code}</span>
      <span className="confidence-badge">
        {(evidence.confidence_score * 100).toFixed(0)}%
      </span>
    </div>
    <div className="evidence-card-meta">
      <span className="page-ref">第 {evidence.source_page} 页</span>
      {evidence.review_required && <span className="review-tag">需审核</span>}
    </div>
  </div>
);

/**
 * 内容区块组件
 */
const ContentSection: React.FC<{
  section: DocumentSection;
  isActive: boolean;
  onVisible: (id: string) => void;
}> = ({ section, isActive, onVisible }) => {
  const sectionRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sectionRef.current) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          onVisible(section.id);
        }
      },
      { threshold: 0.3 }
    );

    observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, [section.id, onVisible]);

  return (
    <section
      ref={sectionRef}
      id={`section-${section.id}`}
      className={`content-section ${isActive ? 'active' : ''}`}
      data-section-type={section.type}
    >
      <h2 className="section-heading">{section.title}</h2>
      <div className="section-content">
        {section.content.split('\n').map((paragraph, idx) => (
          <p key={idx} className="content-paragraph">{paragraph}</p>
        ))}
      </div>
    </section>
  );
};

export const DocumentViewPage: React.FC = () => {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  
  const [document, setDocument] = useState<DocumentData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  // 加载文档
  useEffect(() => {
    if (!documentId) {
      setError('文档ID不能为空');
      setIsLoading(false);
      return;
    }

    const loadDocument = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // 首先尝试从 API 获取
        const response = await getDocument(documentId);
        
        if (response.data) {
          setDocument(response.data as DocumentData);
          // 默认展开第一个章节
          const firstSection = (response.data as DocumentData).sections?.[0];
          if (firstSection) {
            setActiveSectionId(firstSection.id);
            setExpandedSections(new Set([firstSection.id]));
          }
        } else {
          // 如果没有数据，使用模拟数据
          loadMockDocument(documentId);
        }
      } catch (err) {
        console.error('Failed to load document:', err);
        // API 失败时使用模拟数据
        if (documentId === 'demo' || documentId === '12345678') {
          loadMockDocument(documentId);
        } else {
          setError(err instanceof APIError ? err.message : '加载文档失败');
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadDocument();
  }, [documentId]);

  // 加载模拟文档
  const loadMockDocument = (id: string) => {
    const mockDocument: DocumentData = {
      document_id: id,
      pmid: id === 'demo' ? '12345678' : id,
      doi: '10.3969/j.issn.1674-8115.2026.02.001',
      title: '小胶质细胞TRPV1在载脂蛋白E4相关帕金森病中的作用',
      authors: ['张三', '李四', '王五'],
      abstract: '帕金森病(PD)是一种常见的神经退行性疾病...',
      sections: [
        {
          id: 'sec-1',
          type: 'title',
          title: '标题',
          content: '小胶质细胞TRPV1在载脂蛋白E4相关帕金森病中的作用',
          level: 1,
          order: 1,
        },
        {
          id: 'sec-2',
          type: 'abstract',
          title: '摘要',
          content: '目的: 探讨小胶质细胞瞬时受体电位香草酸1型(TRPV1)在载脂蛋白E4(ApoE4)相关帕金森病(PD)中的作用及其机制。\n方法: 使用ApoE4转基因小鼠和TRPV1条件敲除小鼠构建PD模型...\n结果: TRPV1缺失加重了ApoE4相关PD的病理进展...\n结论: 小胶质细胞TRPV1是ApoE4相关PD的潜在治疗靶点。',
          level: 1,
          order: 2,
        },
        {
          id: 'sec-3',
          type: 'background',
          title: '背景',
          content: '帕金森病(PD)是第二常见的神经退行性疾病,其发病率随年龄增长而增加。载脂蛋白E4(ApoE4)是阿尔茨海默病最强的遗传风险因素,也与PD的发病风险和病程进展相关。\n\n瞬时受体电位香草酸1型(TRPV1)是一种非选择性阳离子通道,主要在感觉神经元中表达。近年来研究发现,TRPV1在中枢神经系统的小胶质细胞中也有表达,并参与神经炎症调节。',
          level: 1,
          order: 3,
        },
        {
          id: 'sec-4',
          type: 'objective',
          title: '研究目的',
          content: '本研究旨在探讨小胶质细胞TRPV1在ApoE4相关PD中的作用,以及其作为治疗靶点的潜力。',
          level: 1,
          order: 4,
        },
        {
          id: 'sec-5',
          type: 'methods',
          title: '方法',
          content: '动物模型: 使用ApoE4转基因小鼠和TRPV1条件敲除小鼠。\n\n实验分组: (1)野生型;(2)ApoE4;(3)TRPV1-/-;(4)ApoE4/TRPV1-/-。\n\n行为学测试: 旷场实验、爬杆实验、Morris水迷宫。\n\n组织学分析: 免疫荧光、蛋白质印迹、脂质组学分析。',
          level: 1,
          order: 5,
        },
        {
          id: 'sec-6',
          type: 'results',
          title: '结果',
          content: '行为学结果: E4/Trpv1MGKO小鼠表现出加重的运动功能障碍。旷场实验中平均速度和总移动距离进一步增加(P < 0.05)。\n\n神经元存活: 免疫荧光显示E4/Trpv1MGKO小鼠黑质致密部多巴胺能神经元丢失加重。\n\n病理蛋白: p-α-syn沉积在E4/Trpv1MGKO小鼠中显著增加。\n\n脂质代谢: 小胶质细胞脂质滴积聚增加,提示脂质代谢稳态被破坏。',
          level: 1,
          order: 6,
        },
        {
          id: 'sec-7',
          type: 'conclusion',
          title: '结论',
          content: '小胶质细胞TRPV1缺失加重了ApoE4相关PD的病理进展,包括运动功能障碍、多巴胺能神经元丢失和p-α-syn沉积。机制上,TRPV1缺失导致小胶质细胞吞噬功能增强和脂质代谢紊乱。\n\n这些发现提示小胶质细胞TRPV1可能是ApoE4相关PD的潜在治疗靶点。',
          level: 1,
          order: 7,
        },
      ],
      evidence_items: [
        { id: 'ev1', acmg_code: 'PS1', confidence_score: 0.92, review_required: false, source_page: 5 },
        { id: 'ev2', acmg_code: 'PS4', confidence_score: 0.88, review_required: false, source_page: 6 },
        { id: 'ev3', acmg_code: 'PM1', confidence_score: 0.82, review_required: true, source_page: 8 },
        { id: 'ev4', acmg_code: 'PM2', confidence_score: 0.80, review_required: true, source_page: 9 },
        { id: 'ev5', acmg_code: 'PP3', confidence_score: 0.72, review_required: true, source_page: 10 },
      ],
      metadata: {
        journal: '神经科学杂志',
        publication_date: '2026-02-01',
        keywords: ['TRPV1', 'ApoE4', '帕金森病', '小胶质细胞', '脂质代谢'],
      },
    };

    setDocument(mockDocument);
    setActiveSectionId(mockDocument.sections[0]?.id || null);
    setExpandedSections(new Set(mockDocument.sections.slice(0, 2).map(s => s.id)));
  };

  // 处理章节点击
  const handleSectionClick = useCallback((sectionId: string) => {
    setActiveSectionId(sectionId);
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sectionId)) {
        newSet.delete(sectionId);
      } else {
        newSet.add(sectionId);
      }
      return newSet;
    });

    // 滚动到对应章节
    const element = window.document.getElementById(`section-${sectionId}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  // 处理章节可见性
  const handleSectionVisible = useCallback((sectionId: string) => {
    setActiveSectionId(sectionId);
  }, []);

  // 渲染加载状态
  if (isLoading) {
    return (
      <div className="document-view-page loading">
        <div className="loading-container">
          <Loader2 size={48} className="spin" />
          <p>加载文档中...</p>
        </div>
      </div>
    );
  }

  // 渲染错误状态
  if (error) {
    return (
      <div className="document-view-page error">
        <div className="error-container">
          <AlertCircle size={48} />
          <h2>加载失败</h2>
          <p>{error}</p>
          <button className="btn-primary" onClick={() => navigate(-1)}>
            <ArrowLeft size={16} /> 返回
          </button>
        </div>
      </div>
    );
  }

  // 渲染文档内容
  if (!document) {
    return (
      <div className="document-view-page error">
        <div className="error-container">
          <AlertCircle size={48} />
          <h2>文档不存在</h2>
          <button className="btn-primary" onClick={() => navigate('/')}>返回首页</button>
        </div>
      </div>
    );
  }

  return (
    <div className="document-view-page">
      {/* 侧边导航 */}
      <aside className="document-sidebar">
        <div className="sidebar-header">
          <button className="btn-back" onClick={() => navigate(-1)}>
            <ArrowLeft size={20} />
          </button>
          <h3>文档导航</h3>
        </div>

        {/* 元信息 */}
        <div className="document-meta-sidebar">
          <div className="meta-item">
            <FileText size={14} />
            <span>PMID: {document.pmid || '-'}</span>
          </div>
          {document.doi && (
            <div className="meta-item">
              <Tag size={14} />
              <span>DOI: {document.doi}</span>
            </div>
          )}
          {document.metadata?.publication_date && (
            <div className="meta-item">
              <Calendar size={14} />
              <span>{document.metadata.publication_date}</span>
            </div>
          )}
          {document.authors && (
            <div className="meta-item">
              <User size={14} />
              <span>{document.authors.slice(0, 3).join(', ')}{document.authors.length > 3 ? ' 等' : ''}</span>
            </div>
          )}
        </div>

        {/* 章节导航 */}
        <nav className="section-navigation">
          <h4>章节</h4>
          <div className="section-list">
            {document.sections.map(section => (
              <SectionItem
                key={section.id}
                section={section}
                isActive={activeSectionId === section.id}
                onClick={() => handleSectionClick(section.id)}
                isExpanded={expandedSections.has(section.id)}
              />
            ))}
          </div>
        </nav>

        {/* 证据项列表 */}
        {document.evidence_items && document.evidence_items.length > 0 && (
          <div className="evidence-sidebar">
            <h4>证据项 ({document.evidence_items.length})</h4>
            <div className="evidence-list-mini">
              {document.evidence_items.map(evidence => (
                <EvidenceCard key={evidence.id} evidence={evidence} />
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* 主内容区 */}
      <main className="document-content">
        {/* 文档头部 */}
        <header className="document-header">
          <h1 className="document-title">{document.title}</h1>
          {document.metadata?.keywords && (
            <div className="document-keywords">
              {document.metadata.keywords.map((keyword, idx) => (
                <span key={idx} className="keyword-tag">{keyword}</span>
              ))}
            </div>
          )}
        </header>

        {/* 章节内容 */}
        <div className="sections-container">
          {document.sections.map(section => (
            <ContentSection
              key={section.id}
              section={section}
              isActive={activeSectionId === section.id}
              onVisible={handleSectionVisible}
            />
          ))}
        </div>

        {/* 证据项汇总 */}
        {document.evidence_items && document.evidence_items.length > 0 && (
          <section className="evidence-summary">
            <h2>提取的证据项</h2>
            <div className="evidence-grid">
              {document.evidence_items.map(evidence => (
                <EvidenceCard key={evidence.id} evidence={evidence} />
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
};

export default DocumentViewPage;
