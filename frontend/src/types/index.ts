// Language types supported by the platform
export type Language = 'chinese' | 'japanese' | 'german' | 'french' | 'english';

// ACMG/AMP variant classification
export type VariantClassification = 
  | 'Pathogenic'
  | 'Likely Pathogenic'
  | 'Uncertain Significance'
  | 'Likely Benign'
  | 'Benign';

// Document processing status
export type DocumentStatus = 'uploaded' | 'processing' | 'processed' | 'failed';

// ACMG criteria structure
export interface AcmgCriteria {
  pvs1: boolean;
  ps: string[];
  pm: string[];
  pp: string[];
  ba1: boolean;
  bs: string[];
  bp: string[];
}

// Document model
export interface Document {
  id: string;
  filename: string;
  language: string;
  upload_time: string;
  status: DocumentStatus;
}

// Evidence extracted from document
export interface Evidence {
  id: string;
  variant_id: string;
  gene: string;
  transcript: string | null;
  hgvs_c: string | null;
  hgvs_p: string | null;
  evidence_text: string;
  acmg_criteria: AcmgCriteria;
  suggested_classification: string | null;
  confidence_score: number;
}

// ClinVar validation result
export interface ClinVarResult {
  variant_id: string;
  clinvar_id: string | null;
  review_status: string | null;
  classification: string | null;
  last_evaluated: string | null;
  submitter_count: number;
  condition: string | null;
}

// Analysis result combining evidence and ClinVar data
export interface AnalysisResult {
  id: string;
  document_id: string;
  evidence: Evidence[];
  clinvar_results: ClinVarResult[];
  final_classification: string | null;
  confidence_score: number;
  analysis_time: string;
}

// API response types
export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface UploadResponse {
  id: string;
  filename: string;
  language: string;
  status: string;
  message: string;
}

// Language display configuration
export const languageDisplayNames: Record<Language, string> = {
  chinese: '中文',
  japanese: '日本語',
  german: 'Deutsch',
  french: 'Français',
  english: 'English',
};
