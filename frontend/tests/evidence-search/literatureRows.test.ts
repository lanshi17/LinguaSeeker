import { describe, expect, it } from "vitest";
import {
  buildBilingualCompareHref,
  buildLiteratureRows,
  findInitialEvidenceId,
} from "../../src/features/evidence-search/utils/literatureRows";
import type {
  EvidenceGroupDetailResponse,
  EvidenceSearchResult,
} from "../../src/features/evidence-search/types/evidenceSearch";

const SEARCH_RESULTS: EvidenceSearchResult[] = [
  {
    group_id: "group-a",
    source_document_id: "doc-1",
    pmid: "12345678",
    doi: "10.1000/acmg.1",
    gene: "BRCA1",
    variant: "c.5266dupC",
    disease: "Breast cancer",
    classification: "pathogenic",
    field_count: 12,
    avg_confidence: 0.92,
    review_status: "approved",
    canonical_evidence_id: "ev-a",
  },
  {
    group_id: "group-b",
    source_document_id: "doc-1",
    pmid: "12345678",
    doi: "10.1000/acmg.1",
    gene: "BRCA2",
    variant: "p.Val600Glu",
    disease: "Ovarian cancer",
    classification: "likely pathogenic",
    field_count: 8,
    avg_confidence: 0.82,
    review_status: "provisional",
    canonical_evidence_id: "ev-b",
  },
  {
    group_id: "group-c",
    source_document_id: "doc-2",
    pmid: null,
    doi: null,
    gene: "TP53",
    variant: null,
    disease: "Li-Fraumeni syndrome",
    classification: null,
    field_count: 3,
    avg_confidence: null,
    review_status: "rejected",
    canonical_evidence_id: null,
  },
];

const DETAIL: EvidenceGroupDetailResponse = {
  group_id: "group-a",
  source_document_id: "doc-1",
  pmid: "12345678",
  doi: "10.1000/acmg.1",
  gene: "BRCA1",
  variant: "c.5266dupC",
  disease: "Breast cancer",
  classification: "pathogenic",
  item_count: 2,
  avg_confidence: 0.91,
  distribution: {
    by_category: {},
    by_field: {},
    by_status: {},
    by_track: {},
  },
  items: [
    {
      canonical_evidence_id: "ev-a",
      field_id: "variant_classification",
      review_status: "approved",
      value: "pathogenic",
    },
    {
      canonical_evidence_id: "ev-b",
      field_id: "functional_assay",
      review_status: "provisional",
      value: "reduced DNA repair activity",
    },
  ],
  traces: [
    {
      canonical_evidence_id: "ev-b",
      field_id: "functional_assay",
      alignment_confidence: 0.88,
      original: {
        text: "The assay showed reduced DNA repair activity.",
        highlight_start: 17,
        highlight_end: 43,
        source_span: {},
      },
      translated: {
        text: "该实验显示 DNA 修复活性降低。",
        highlight_start: 6,
        highlight_end: 18,
        source_span: {},
      },
    },
  ],
};

describe("buildLiteratureRows", () => {
  it("groups evidence search results into literature-level rows", () => {
    const rows = buildLiteratureRows(SEARCH_RESULTS);

    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      documentId: "doc-1",
      representativeGroupId: "group-a",
      pmid: "12345678",
      doi: "10.1000/acmg.1",
      fieldCount: 20,
      groupCount: 2,
      reviewStatus: "mixed",
    });
    expect(rows[0].genes).toEqual(["BRCA1", "BRCA2"]);
    expect(rows[0].variants).toEqual(["c.5266dupC", "p.Val600Glu"]);
    expect(rows[0].diseases).toEqual(["Breast cancer", "Ovarian cancer"]);
    expect(rows[0].classifications).toEqual([
      "pathogenic",
      "likely pathogenic",
    ]);
    expect(rows[0].avgConfidence).toBeCloseTo(0.88);
  });
});

describe("bilingual comparison helpers", () => {
  it("selects a requested evidence id when it exists", () => {
    expect(findInitialEvidenceId(DETAIL, "ev-b")).toBe("ev-b");
  });

  it("falls back to the first traceable evidence item", () => {
    expect(findInitialEvidenceId(DETAIL, "missing")).toBe("ev-b");
  });

  it("builds a stable href for the bilingual comparison view", () => {
    expect(buildBilingualCompareHref("group-a", "ev-b")).toBe(
      "/evidence/detail?groupId=group-a&view=compare&evidenceId=ev-b",
    );
  });
});
