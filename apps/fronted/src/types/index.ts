/**
 * 核心类型定义
 */

// 导出 API 类型
export * from './api';

// 证据类型常量对象
export const EvidenceType = {
  PVS: 'PVS',
  PS: 'PS',
  PM: 'PM',
  PP: 'PP',
  BA: 'BA',
  BS: 'BS',
  BP: 'BP',
} as const;

export type EvidenceTypeValue = typeof EvidenceType[keyof typeof EvidenceType];

// 证据类型颜色映射
export const EvidenceTypeColors: Record<EvidenceTypeValue, string> = {
  [EvidenceType.PVS]: '#dc2626',
  [EvidenceType.PS]: '#ea580c',
  [EvidenceType.PM]: '#ca8a04',
  [EvidenceType.PP]: '#16a34a',
  [EvidenceType.BA]: '#2563eb',
  [EvidenceType.BS]: '#7c3aed',
  [EvidenceType.BP]: '#db2777',
};

// 生物实体类型
export type EntityType = 
  | 'keyword' 
  | 'gene' 
  | 'transcript' 
  | 'variant' 
  | 'protein' 
  | 'pathway'
  | 'disease'
  | 'evidence' 
  | 'document';

// 文本位置
export interface TextPosition {
  id: string;
  startOffset: number;
  endOffset: number;
  paragraphIndex: number;
  pageNumber?: number;
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

// 双语定位信息
export interface BilingualPosition {
  original: TextPosition;
  translated: TextPosition;
}

// 证据项
export interface Evidence {
  id: string;
  type: EvidenceTypeValue;
  keyword: string;
  originalKeyword?: string;  // 原文关键词（如果与keyword不同）
  description: string;
  originalDescription?: string;  // 原文描述
  positions: TextPosition[];  // 原文位置
  translatedPositions?: TextPosition[];  // 译文位置（可选，用于精确对齐）
  bilingualPositions?: BilingualPosition[];  // 双语配对位置（推荐）
  confidence: number;
  metadata?: {
    gene?: string;
    variant?: string;
    pmid?: string;
  };
}

// 图片资源
export interface ImageResource {
  filename: string;
  url: string;
  width?: number;
  height?: number;
}

// 文档数据
export interface DocumentData {
  id: string;
  pmid?: string;
  doi?: string;
  title: string;
  originalMarkdown: string;
  translatedMarkdown: string;
  pdfUrl?: string;
  evidences: Evidence[];
  images?: ImageResource[];
  createdAt: string;
  metadata?: {
    authors?: string[];
    journal?: string;
    year?: number;
    abstract?: string;
  };
}

// 图谱节点
export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  evidenceType?: EvidenceTypeValue;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  metadata?: Record<string, unknown>;
}

// 图谱边
export interface GraphEdge {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  weight: number;
  relation?: string;
}

// 图谱数据
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// 三屏联动状态
export interface TriplePanelState {
  activeEvidenceId: string | null;
  scrollRatio: number;
  highlightedPosition: TextPosition | null;
  pdfPage: number;
}

// URL查询参数
export interface ViewStateParams {
  docId?: string;
  evidenceId?: string;
  position?: string;
  panel?: 'original' | 'translated';
  page?: string;
}

// 章节结构（用于语义对齐）
export interface Chapter {
  id: string;
  level: number;
  title: string;
  index: number;
  charOffset: number;
}

// 任务状态
export interface TaskStatus {
  id: string;
  type: 'upload' | 'pmid' | 'doi' | 'url';
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  error?: string;
  result?: DocumentData;
}
