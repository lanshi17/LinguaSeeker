export type EvidenceHighlight = {
  kind: 'evidence' | 'acmg' | 'user';
  sourceRanges?: Array<{ start: number; end: number }>;
  targetRanges?: Array<{ start: number; end: number }>;
  label?: string;
};

export type EvidenceSegment = {
  id: string;
  sourceText: string;
  targetText: string;
  groupId?: string;
  highlights?: EvidenceHighlight[];
};

export type EvidenceViewModel = {
  sourceLang: string;
  targetLang: string;
  segments: EvidenceSegment[];
  raw?: unknown;
  warning?: string;
};

// ==================== Extracted Evidence Field Types ====================

export type GeneInfo = {
  symbol: string;
  full_name?: string | null;
  ncbi_gene_id?: string | null;
  ensembl_id?: string | null;
  confidence: number;
  evidence_quote?: string | null;
};

export type TranscriptInfo = {
  transcript_id: string;
  source?: string | null;
  confidence: number;
  evidence_quote?: string | null;
};

export type ReferenceGenomeInfo = {
  version: string;
  confidence: number;
  evidence_quote?: string | null;
};

export type ExperimentData = {
  assay_type: string;
  method_description?: string | null;
  key_findings?: string[] | null;
  statistical_data?: Record<string, unknown> | null;
  sample_size?: string | null;
  cell_line?: string | null;
  model_organism?: string | null;
  confidence: number;
  evidence_quote?: string | null;
};

export type DiseaseInfo = {
  disease_name: string;
  chpo_id?: string | null;
  icd10_code?: string | null;
  omim_id?: string | null;
  inheritance_pattern?: string | null;
  confidence: number;
  evidence_quote?: string | null;
};

export type SpeciesInfo = {
  species_name: string;
  is_human: boolean;
  confidence: number;
  evidence_quote?: string | null;
};

export type PhenotypeInfo = {
  phenotype_description: string;
  hpo_ids?: string[] | null;
  severity?: string | null;
  onset_age?: string | null;
  confidence: number;
  evidence_quote?: string | null;
};

export type VariantInfo = {
  hgvs_c?: string | null;
  hgvs_p?: string | null;
  hgvs_g?: string | null;
  chromosome?: string | null;
  position?: number | null;
  ref_allele?: string | null;
  alt_allele?: string | null;
  variant_type?: string | null;
  rs_id?: string | null;
  clinvar_id?: string | null;
  confidence: number;
  evidence_quote?: string | null;
};

export type ControlInfo = {
  has_negative_control: boolean;
  has_positive_control: boolean;
  negative_control_description?: string | null;
  positive_control_description?: string | null;
  control_variants?: Array<Record<string, unknown>> | null;
  total_control_count: number;
  confidence: number;
  evidence_quote?: string | null;
};

export type PedigreeInfo = {
  has_pedigree: boolean;
  family_size?: number | null;
  affected_count?: number | null;
  segregation_data?: string | null;
  inheritance_pattern?: string | null;
  confidence: number;
  evidence_quote?: string | null;
};

export type ExtractedEvidenceFields = {
  gene?: GeneInfo | null;
  transcript_id?: TranscriptInfo | null;
  reference_genome_version?: ReferenceGenomeInfo | null;
  experiment_data?: ExperimentData | null;
  disease_chpo?: DiseaseInfo | null;
  disease_icd10?: DiseaseInfo | null;
  species?: SpeciesInfo | null;
  phenotype?: PhenotypeInfo | null;
  variant?: VariantInfo | null;
  negative_positive_control?: ControlInfo | null;
  pedigree_information?: PedigreeInfo | null;
};

export type EvidenceRecord = {
  evidence_id?: number | null;
  document_id?: string | null;
  gene_symbol?: string | null;
  variant_hgvs_c?: string | null;
  variant_hgvs_p?: string | null;
  protein_change?: string | null;
  transcript_id?: string | null;
  reference_genome?: string | null;
  disease_name?: string | null;
  icd10_code?: string | null;
  species?: string | null;
  phenotype?: string | null;
  evidence_strength?: string | null;
  evidence_classification?: string | null;
  overall_confidence?: number | null;
  arbitration_score?: number | null;
  is_valid?: string | null;
  acmg_levels?: string[] | null;
  extracted_fields?: ExtractedEvidenceFields | null;
  ps3_evidence?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type EvidenceSearchData = {
  evidence_records?: EvidenceRecord[];
  document_count?: number;
  total_evidence?: number;
  nodes?: Array<Record<string, unknown>>;
  edges?: Array<Record<string, unknown>>;
};
