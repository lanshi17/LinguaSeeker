/**
 * 医学证据分析类型定义
 */

/** 证据类型 */
export type EvidenceType = 'text' | 'image';

/** 证据用途分类 */
export type EvidencePurpose = 
  | 'disease_mechanism' 
  | 'assay_setup' 
  | 'controls_replicates' 
  | 'assay_result'
  | 'other';

/** 证据定位信息 */
export interface EvidenceLocator {
  file: string;
  char_start?: number | null;
  char_end?: number | null;
  line_start?: number | null;
  line_end?: number | null;
}

/** 证据关键词 */
export interface EvidenceKeywords {
  raw: string[];
  normalized: string[];
  tex_wrapped?: string[];
}

/** 证据项 */
export interface EvidenceItem {
  id: string;
  type: EvidenceType;
  purpose: EvidencePurpose;
  locator: EvidenceLocator;
  quote?: string;
  keywords: EvidenceKeywords;
  image_ref?: string;
}

/** 证据分析结果 */
export interface EvidenceAnalysis {
  evidence_items: EvidenceItem[];
  metadata?: {
    document_id?: string;
    analysis_date?: string;
    version?: string;
  };
}

/** 高亮范围 */
export interface HighlightRange {
  start: number;
  end: number;
  evidenceId: string;
  purpose: EvidencePurpose;
}

/** 图片引用映射 */
export interface ImageReference {
  ref: string;
  alt: string;
  src: string;
  evidenceIds: string[];
}

/** 证据分组 */
export interface EvidenceGroup {
  purpose: EvidencePurpose;
  label: string;
  items: EvidenceItem[];
}

/** 用途标签映射 */
export const PURPOSE_LABELS: Record<EvidencePurpose, string> = {
  disease_mechanism: '疾病机制',
  assay_setup: '实验设置',
  controls_replicates: '对照与重复',
  assay_result: '实验结果',
  other: '其他',
};

/** 用途颜色映射 */
export const PURPOSE_COLORS: Record<EvidencePurpose, string> = {
  disease_mechanism: '#ff4d4f',
  assay_setup: '#1890ff',
  controls_replicates: '#52c41a',
  assay_result: '#faad14',
  other: '#8c8c8c',
};
