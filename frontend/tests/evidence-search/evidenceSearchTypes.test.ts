import type { EvidenceGroupDetailResponse } from "../../src/features/evidence-search/types/evidenceSearch";

const detailWithAlignment: EvidenceGroupDetailResponse = {
  group_id: "gene=['MECP2']|variant=['c.194delC']",
  source_document_id: "doc-1",
  title: "MECP2 case report",
  pmid: null,
  doi: null,
  gene: "MECP2",
  variant: "c.194delC",
  disease: "Rett syndrome",
  classification: null,
  item_count: 1,
  avg_confidence: 0.92,
  distribution: {
    by_category: { A: 1 },
    by_field: { "A.variant_hgvs_c": 1 },
    by_status: { provisional: 1 },
    by_track: { translated: 1 },
  },
  items: [
    {
      canonical_evidence_id: "evidence-1",
      field_id: "A.variant_hgvs_c",
      field_name: "Variant HGVS",
      category: "A",
      value: "c.194delC",
      review_status: "provisional",
      confidence: 0.92,
      track: "translated",
      page: 1,
    },
  ],
  traces: [],
  translation_alignment: [
    {
      chunk_id: "c_0001",
      original_text: "MECP2基因存在c.194delC致病性突变。",
      english_text: "A pathogenic c.194delC mutation was found in MECP2.",
      original_start_offset: 0,
      original_end_offset: 27,
      english_start_offset: 0,
      english_end_offset: 54,
      page: 1,
      block_index: 0,
      bbox: [],
      span_pairs: [
        {
          pair_id: "c_0001-p_0001",
          original_text: "c.194delC",
          english_text: "c.194delC",
          original_start_offset: 8,
          original_end_offset: 17,
          english_start_offset: 14,
          english_end_offset: 23,
          confidence: 0.96,
          method: "semantic_llm",
        },
      ],
    },
  ],
};

if (detailWithAlignment.translation_alignment?.[0]?.span_pairs?.[0]?.english_text !== "c.194delC") {
  throw new Error("Evidence detail alignment fixture is invalid.");
}
