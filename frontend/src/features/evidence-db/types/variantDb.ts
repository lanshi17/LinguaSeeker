// Reuse existing types from evidence-search
import type { EvidenceSearchResult, EvidenceGroupDetailResponse, EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";
import type {
  LiteratureQualitySummary,
  ReviewProgress,
  VariantQualitySummary,
} from "../utils/fieldModel";

/** Classification severity level for pathogenicity ordering */
export type ClassificationLevel = "pathogenic" | "likely_pathogenic" | "uncertain" | "likely_benign" | "benign";

/** L1: Aggregated variant entry — one row in the variant index */
export interface VariantIndexEntry {
  /** Composite key: "GENE:VARIANT" or "GENE:VARIANT:DISEASE" */
  variantSlug: string;
  gene: string;
  variant: string;
  disease: string;
  classification: string;
  classificationLevel: ClassificationLevel;
  /** Number of evidence groups (source documents) for this variant */
  evidenceGroupCount: number;
  /** Number of unique source documents */
  literatureCount: number;
  /** Weighted average confidence across all evidence items */
  avgConfidence: number;
  /** Number of distinct evidence fields found */
  fieldCount: number;
  /** Category distribution: { "A": 5, "B": 3, ... } */
  categoryDistribution: Record<string, number>;
  /** Aggregate review status — worst-case wins */
  reviewStatus: string;
  /** Aggregate review progress across grouped search rows. */
  reviewProgress: ReviewProgress;
  /** Most recent created_at from grouped evidence */
  createdAt?: string | null;
  /** All group_ids that belong to this variant */
  groupIds: string[];
  /** All unique source_document_ids */
  sourceDocumentIds: string[];
  /** Exact group/document pairs represented by this row. */
  groupDocumentPairs: Array<{ groupId: string; sourceDocumentId: string }>;
  /** Representative search result (for navigation) */
  representative: EvidenceSearchResult;
}

/** L1: Paginated variant index response (client-side computed) */
export interface VariantIndexData {
  items: VariantIndexEntry[];
  total: number;
  page: number;
  pageSize: number;
  /** Aggregate stats across all variants */
  stats: {
    totalVariants: number;
    totalEvidenceGroups: number;
    totalLiterature: number;
    avgConfidence: number;
    classificationDistribution: Record<ClassificationLevel, number>;
  };
}

/** L2: Variant detail — all evidence for a single variant */
export interface VariantDetailData {
  entry: VariantIndexEntry;
  /** All evidence groups with their full details */
  evidenceGroups: EvidenceGroupDetailResponse[];
  /** Literature references aggregated from evidence groups */
  literature: LiteratureReference[];
  /** All evidence items flattened from all groups */
  allItems: EvidenceGroupItem[];
  /** Only reconciled-track items (primary display) */
  reconciledItems: EvidenceGroupItem[];
  /** Original + translated items keyed by canonical_evidence_id for bilingual display */
  bilingualItems: Map<string, { original?: EvidenceGroupItem; translated?: EvidenceGroupItem }>;
  /** Derived evidence-quality metrics for this variant. */
  quality: VariantQualitySummary;
}

/** L2: A single literature reference in the variant's reference list */
export interface LiteratureReference extends LiteratureQualitySummary {
  sourceDocumentId: string;
  title: string;
  pmid?: string;
  doi?: string;
  groupId: string;
  fieldCount: number;
  avgConfidence: number;
  reviewStatus: string;
  categories: string[];
  /** Original + translated items for bilingual display in References */
  bilingualItems: Map<string, { original?: EvidenceGroupItem; translated?: EvidenceGroupItem }>;
}

/** Sort direction */
export type SortOrder = "asc" | "desc";

/** Sortable column keys */
export type SortBy =
  | "gene"
  | "variant"
  | "disease"
  | "classification"
  | "evidence"
  | "refs"
  | "confidence"
  | "updated";

/** Review-status filter values */
export type ReviewStatusFilter = "provisional" | "approved" | "corrected" | "rejected";

/** Search/filter state for the variant index */
export interface VariantIndexFilters {
  gene?: string;
  variant?: string;
  disease?: string;
  classification?: ClassificationLevel;
  reviewStatus?: ReviewStatusFilter;
  page: number;
  pageSize: number;
  sortBy?: SortBy;
  sortOrder?: SortOrder;
}
