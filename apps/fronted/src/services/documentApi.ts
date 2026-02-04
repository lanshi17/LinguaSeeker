/**
 * 文档 API 服务
 * 
 * 后续对接后端 API 接口：
 * 
 * ## 后端 API 规范
 * 
 * ### 1. 获取文档
 * GET /api/v1/documents/:id
 * 
 * Response:
 * {
 *   id: string;
 *   pmid?: string;
 *   title: string;
 *   originalMarkdown: string;      // 原文 Markdown
 *   translatedMarkdown: string;    // 英文翻译 Markdown
 *   evidences: Evidence[];         // 证据列表
 *   images: {                      // 图片资源映射
 *     [filename: string]: string;  // 文件名 -> 图片URL
 *   };
 *   createdAt: string;
 * }
 * 
 * ### 2. 上传 PDF
 * POST /api/v1/documents/upload
 * Content-Type: multipart/form-data
 * 
 * Response:
 * {
 *   id: string;        // 新文档ID
 *   status: "processing" | "completed";
 * }
 * 
 * ### 3. 通过 PMID 获取
 * GET /api/v1/documents/pmid/:pmid
 * 
 * Response: 同 (1)
 * 
 * ### 4. 搜索图谱
 * GET /api/v1/graph/search?keyword=xxx
 * 
 * Response:
 * {
 *   nodes: GraphNode[];
 *   edges: GraphEdge[];
 * }
 * 
 * ## 关于图片处理
 * 
 * Markdown 中的图片引用格式: `![](images/filename.jpg)`
 * 
 * 后端需要：
 * 1. 返回图片的 URL 映射表 { [filename]: url }
 * 2. 或直接在 Markdown 中替换为完整 URL
 * 3. 或提供图片下载接口 /api/v1/documents/:id/images/:filename
 */
import type { DocumentData, Evidence, GraphData } from '../types';
import evidenceData from '../../test_document/evidence.json';

const API_BASE = '/api/v1';

// ==================== 后端 API 接口 ====================

/**
 * 从后端 API 获取文档
 * GET /api/v1/documents/:id
 */
async function fetchFromAPI(id: string): Promise<DocumentData> {
  const response = await fetch(`${API_BASE}/documents/${id}`);
  
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('文档不存在');
    }
    throw new Error(`API 错误: ${response.status}`);
  }
  
  const data = await response.json();
  
  // 处理图片路径：后端返回的 Markdown 中图片路径可能需要处理
  // 方式1: 后端直接返回带完整 URL 的 Markdown
  // 方式2: 后端返回图片映射表，前端替换
  if (data.images && typeof data.images === 'object') {
    // 替换 Markdown 中的图片路径
    Object.entries(data.images).forEach(([filename, url]) => {
      const regex = new RegExp(`!\\[(.*?)\\]\\(.*?${filename}.*?\\)`, 'g');
      const replacement = `![$1](${url})`;
      data.originalMarkdown = data.originalMarkdown.replace(regex, replacement);
      data.translatedMarkdown = data.translatedMarkdown.replace(regex, replacement);
    });
  }
  
  return data;
}

/**
 * 上传 PDF 文件解析
 * POST /api/v1/documents/upload
 */
export async function uploadDocument(file: File): Promise<{ id: string; status: string }> {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error('上传失败');
  }
  
  return response.json();
}

/**
 * 通过 PMID 获取文献
 * GET /api/v1/documents/pmid/:pmid
 */
export async function fetchByPMID(pmid: string): Promise<DocumentData> {
  const response = await fetch(`${API_BASE}/documents/pmid/${pmid}`);
  
  if (!response.ok) {
    throw new Error('文献获取失败');
  }
  
  return response.json();
}

/**
 * 获取文档中的图片
 * GET /api/v1/documents/:id/images/:filename
 */
export function getDocumentImageUrl(docId: string, filename: string): string {
  return `${API_BASE}/documents/${docId}/images/${filename}`;
}

/**
 * 搜索关键词图谱
 * GET /api/v1/graph/search?keyword=xxx
 */
export async function searchGraph(keyword: string): Promise<GraphData> {
  const response = await fetch(`${API_BASE}/graph/search?keyword=${encodeURIComponent(keyword)}`);
  
  if (!response.ok) {
    throw new Error('搜索失败');
  }
  
  return response.json();
}

// ==================== Demo 模式（开发/测试用）====================

let demoDocumentCache: DocumentData | null = null;

// Evidence JSON type definitions
interface EvidenceJson {
  document_name: string;
  document_topic: string;
  evidence_extraction: {
    metadata: {
      authors: string[];
      institution: string;
      doi: string;
    };
    objective_evidence: {
      content: string;
      key_concepts: string[];
    };
    methods_evidence: Array<{
      content: string;
      key_elements: string[];
    }>;
    results_evidence: Array<{
      content: string;
      key_findings: string[];
    }>;
    conclusion_evidence: {
      content: string;
      key_conclusions: string[];
    };
    background_evidence: Array<{
      content: string;
      key_points: string[];
    }>;
    statistical_evidence: {
      content: string;
      significance: string[];
    };
    pathological_mechanisms: Array<{
      content: string;
      mechanism: string[];
    }>;
  };
  acmg_relevance: {
    ps3_considerations: Array<{
      aspect: string;
      evidence: string;
      strength: string;
    }>;
    clinical_relevance: {
      disease: string;
      genetic_factor: string;
      therapeutic_target: string;
    };
  };
}

/**
 * Transform evidence.json to Evidence array
 */
function transformEvidence(data: EvidenceJson): Evidence[] {
  const evidences: Evidence[] = [];
  let idCounter = 0;

  // Helper to create evidence item
  const createEvidence = (
    type: 'PVS' | 'PS' | 'PM' | 'PP' | 'BA' | 'BS' | 'BP',
    keyword: string,
    description: string,
    confidence: number
  ): Evidence => ({
    id: `ev-${type.toLowerCase()}-${idCounter++}`,
    type,
    keyword,
    description,
    positions: [{ id: `ev-pos-${idCounter}`, startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
    confidence,
  });

  const extraction = data.evidence_extraction;

  // Statistical evidence -> PS (Strong)
  if (extraction.statistical_evidence) {
    evidences.push(createEvidence('PS', 'P = 0.007', 
      'PS4: Statistically significant differences in open field experiments support aggravated motor dysfunction in ApoE4-associated PD mice with TRPV1 deficiency',
      0.92
    ));
    evidences.push(createEvidence('PS', 'P < 0.05',
      'PS4: Further increased average speed and travel distance in E4/Trpv1MGKO mice with AAV-hα-syn injection (both P < 0.05)',
      0.88
    ));
  }

  // Results evidence -> PS/PM based on strength
  if (extraction.results_evidence) {
    extraction.results_evidence.forEach((result) => {
      const content = result.content.toLowerCase();
      
      if (content.includes('motor dysfunction') || content.includes('aggravated')) {
        evidences.push(createEvidence('PS', 'aggravated motor dysfunction',
          'PS4: E4/Trpv1MGKO (AAV-hα-syn) mice showed aggravated motor dysfunction including increased velocity, prolonged pole test times, and dystonic postures',
          0.90
        ));
      }
      
      if (content.includes('spatial learning') || content.includes('morris water maze')) {
        evidences.push(createEvidence('PS', 'impaired spatial learning',
          'PS4: Morris water maze demonstrated significantly prolonged escape latency and reduced target quadrant travel in E4/Trpv1MGKO mice',
          0.85
        ));
      }
      
      if (content.includes('dopaminergic neuron') || content.includes('neuron loss')) {
        evidences.push(createEvidence('PM', 'dopaminergic neuron loss',
          'PM1: Immunofluorescence revealed aggravated loss of dopaminergic neurons in the SNpc of E4/Trpv1MGKO (AAV-hα-syn) mice',
          0.82
        ));
      }
      
      if (content.includes('p-α-syn') || content.includes('deposition')) {
        evidences.push(createEvidence('PM', 'p-α-syn deposition',
          'PM1: Increased p-α-syn deposition in the SNpc observed in microglia-specific TRPV1 knockout mice',
          0.80
        ));
      }
      
      if (content.includes('phagocytosis')) {
        evidences.push(createEvidence('PM', 'enhanced microglial phagocytosis',
          'PM1: Enhanced phagocytosis of microglia in the mesencephalon with increased lipid droplet accumulation',
          0.78
        ));
      }
      
      if (content.includes('lipid droplet')) {
        evidences.push(createEvidence('PM', 'lipid droplet accumulation',
          'PM1: Increased accumulation of lipid droplets in microglia indicating disrupted lipid metabolic homeostasis',
          0.78
        ));
      }
    });
  }

  // Pathological mechanisms -> PM/PP
  if (extraction.pathological_mechanisms) {
    extraction.pathological_mechanisms.forEach((mech) => {
      if (mech.content.includes('lipid droplets') && mech.content.includes('microglia')) {
        evidences.push(createEvidence('PM', 'microglia-specific lipid accumulation',
          'PM1: Microglia-specific Trpv1 knockout significantly increased lipid droplet accumulation in microglia but not in neurons or astrocytes',
          0.80
        ));
      }
      
      if (mech.content.includes('phagocytosis') && mech.content.includes('p-α-syn')) {
        evidences.push(createEvidence('PP', 'enhanced p-α-syn phagocytosis',
          'PP3: TRPV1 deletion enhanced ApoE4-induced phagocytosis of p-α-syn by mesencephalic microglia',
          0.72
        ));
      }
    });
  }

  // Conclusion evidence -> PS
  if (extraction.conclusion_evidence) {
    evidences.push(createEvidence('PS', 'TRPV1 deficiency accelerates pathology',
      'PS3: TRPV1 deficiency in microglia accelerates the pathological progression of ApoE4-associated PD and disrupts lipid metabolic homeostasis',
      0.88
    ));
  }

  // Background evidence -> PP (Supporting)
  if (extraction.background_evidence) {
    extraction.background_evidence.forEach((bg) => {
      if (bg.content.includes('APOE4') || bg.content.includes('cognitive decline')) {
        evidences.push(createEvidence('PP', 'APOE4 and cognitive decline',
          'PP5: APOE4 is closely related to accelerated decline of cognitive function and early onset of dementia in PD patients',
          0.70
        ));
      }
      
      if (bg.content.includes('TRPV1') && bg.content.includes('neuroprotective')) {
        evidences.push(createEvidence('PP', 'TRPV1 neuroprotective effects',
          'PP5: TRPV1 shows neuroprotective effects and potential as a therapeutic target in neurodegenerative diseases',
          0.68
        ));
      }
    });
  }

  // Remove duplicates based on keyword
  const seen = new Set<string>();
  return evidences.filter(ev => {
    if (seen.has(ev.keyword)) return false;
    seen.add(ev.keyword);
    return true;
  });
}

/**
 * 从本地 public/documents 加载 demo 数据
 * 
 * 本地目录结构:
 * public/documents/
 *   ├── test_origin.md
 *   ├── test_translation.md
 *   └── images/
 *       ├── xxx.jpg
 *       └── ...
 */
async function fetchDemoDocument(): Promise<DocumentData> {
  if (demoDocumentCache) {
    return demoDocumentCache;
  }
  
  // 并行加载本地 md 文件
  const [originalRes, translatedRes] = await Promise.all([
    fetch('/documents/test_origin.md'),
    fetch('/documents/test_translation.md'),
  ]);

  if (!originalRes.ok || !translatedRes.ok) {
    throw new Error('Demo document loading failed');
  }

  let [originalMarkdown, translatedMarkdown] = await Promise.all([
    originalRes.text(),
    translatedRes.text(),
  ]);

  // Extract only Chinese content from original (before the first '---' separator)
  // The test_origin.md file contains both Chinese and English, we only want Chinese
  const firstSeparator = originalMarkdown.search(/^---\s*$/m);
  if (firstSeparator > 0) {
    originalMarkdown = originalMarkdown.substring(0, firstSeparator).trim();
  }

  // 处理本地图片路径：将相对路径转为绝对路径
  // 原: ![](images/xxx.jpg)
  // 改: ![](http://localhost:5173/documents/images/xxx.jpg)
  const imageBaseUrl = `${window.location.origin}/documents/images`;
  originalMarkdown = originalMarkdown.replace(
    /!\[(.*?)\]\(images\/([^)]+)\)/g,
    `![$1](${imageBaseUrl}/$2)`
  );
  translatedMarkdown = translatedMarkdown.replace(
    /!\[(.*?)\]\(images\/([^)]+)\)/g,
    `![$1](${imageBaseUrl}/$2)`
  );

  // Load actual evidence from imported evidence.json
  let evidences: Evidence[] = [];
  try {
    evidences = transformEvidence(evidenceData as EvidenceJson);
  } catch (err) {
    console.warn('Failed to transform evidence data, using fallback:', err);
  }

  // Fallback to hardcoded evidence if loading fails
  if (evidences.length === 0) {
    evidences = [
      {
        id: 'ev-ps-1',
        type: 'PS' as const,
        keyword: 'P = 0.007',
        description: 'PS4: Significant statistical difference supporting aggravated motor dysfunction with TRPV1 deficiency',
        positions: [{ id: 'ev-ps-1-0', startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
        confidence: 0.92,
      },
      {
        id: 'ev-ps-2',
        type: 'PS' as const,
        keyword: 'P < 0.05',
        description: 'PS4: Statistically significant, supporting reliability of behavioral differences',
        positions: [{ id: 'ev-ps-2-0', startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
        confidence: 0.88,
      },
    ];
  }

  demoDocumentCache = {
    id: 'demo',
    pmid: '12345678',
    doi: '10.3969/j.issn.1674-8115.2026.02.001',
    title: 'Role of microglia TRPV1 in apolipoprotein E4 associated Parkinson\'s disease',
    originalMarkdown,
    translatedMarkdown,
    evidences,
    createdAt: '2024-01-15',
  };

  return demoDocumentCache;
}

// ==================== 统一的文档获取接口 ====================

/**
 * 获取文档（自动判断 demo/API 模式）
 * 
 * 使用策略：
 * - id === 'demo' 或 id === '12345678': 使用本地 demo 数据
 * - 其他 id: 调用后端 API
 */
export async function getDocument(id: string): Promise<DocumentData> {
  if (id === 'demo' || id === '12345678') {
    return fetchDemoDocument();
  }
  
  return fetchFromAPI(id);
}

/**
 * 预加载文档（可选优化）
 */
export function preloadDocument(id: string): void {
  if (id === 'demo') {
    fetchDemoDocument().catch(console.error);
  }
}

export default {
  getDocument,
  uploadDocument,
  fetchByPMID,
  searchGraph,
  getDocumentImageUrl,
  preloadDocument,
};
