import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  buildBilingualCompareHref,
  buildLiteratureRows,
  findInitialEvidenceId,
} from "../../src/features/evidence-search/utils/literatureRows";
import {
  buildEvidenceDocument,
  countEvidenceHighlightTones,
} from "../../src/features/evidence-search/utils/evidenceDocument";
import type {
  EvidenceGroupDetailResponse,
  EvidenceSearchResult,
} from "../../src/features/evidence-search/types/evidenceSearch";

const SEARCH_RESULTS: EvidenceSearchResult[] = [
  {
    group_id: "group-a",
    source_document_id: "doc-1",
    title: "BRCA1 clinical evidence paper",
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
  title: "BRCA1 clinical evidence paper",
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
      field_id: "J.authority_classification",
      category: "J",
      review_status: "approved",
      value: "pathogenic",
    },
    {
      canonical_evidence_id: "ev-b",
      field_id: "F.functional_assay",
      category: "F",
      review_status: "provisional",
      value: "reduced DNA repair activity",
    },
  ],
  traces: [
    {
      canonical_evidence_id: "ev-b",
      field_id: "F.functional_assay",
      field_name: "Functional assay",
      original_value: "reduced DNA repair activity",
      translated_value: "DNA 修复活性降低",
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

    assert.equal(rows.length, 2);
    // Guard against misspelled property names: verify key fields are not undefined
    assert.ok(rows[0].documentId !== undefined, "documentId must be defined");
    assert.ok(rows[0].representativeGroupId !== undefined, "representativeGroupId must be defined");
    assert.equal(rows[0].documentId, "doc-1");
    assert.equal(rows[0].representativeGroupId, "group-a");
    assert.equal(rows[0].title, "BRCA1 clinical evidence paper");
    assert.equal(rows[0].pmid, "12345678");
    assert.equal(rows[0].doi, "10.1000/acmg.1");
    assert.equal(rows[0].fieldCount, 20);
    assert.equal(rows[0].groupCount, 2);
    assert.equal(rows[0].reviewStatus, "mixed");
    assert.deepEqual(rows[0].genes, ["BRCA1", "BRCA2"]);
    assert.deepEqual(rows[0].variants, ["c.5266dupC", "p.Val600Glu"]);
    assert.deepEqual(rows[0].diseases, ["Breast cancer", "Ovarian cancer"]);
    assert.deepEqual(rows[0].classifications, [
      "pathogenic",
      "likely pathogenic",
    ]);
    // Verify avgConfidence is a number (not falsy-gated — 0 is a valid value)
    const firstAvgConfidence = rows[0].avgConfidence;
    if (typeof firstAvgConfidence !== "number") {
      throw new Error("avgConfidence must be a number");
    }
    // Weighted avg: (0.92*12 + 0.82*8) / 20 = 0.88. Tolerance matches toBeCloseTo default (0.005).
    assert.ok(Math.abs(firstAvgConfidence - 0.88) < 0.005);

    // Verify rows[1] (doc-2 with null fields) — prevents null-aggregation regressions
    assert.equal(rows[1].documentId, "doc-2");
    assert.ok(!rows[1].title, "title should be absent for doc-2");
    assert.equal(rows[1].pmid, null);
    assert.equal(rows[1].doi, null);
    assert.equal(rows[1].avgConfidence, null);
    assert.deepEqual(rows[1].classifications, []);
    assert.deepEqual(rows[1].variants, []);
    assert.equal(rows[1].reviewStatus, "rejected");
    assert.equal(rows[1].groupCount, 1);
  });
});

describe("bilingual comparison helpers", () => {
  it("selects a requested evidence id when it exists", () => {
    assert.equal(findInitialEvidenceId(DETAIL, "ev-b"), "ev-b");
  });

  it("falls back to the first traceable evidence item", () => {
    assert.equal(findInitialEvidenceId(DETAIL, "missing"), "ev-b");
  });

  it("builds a stable href for the bilingual comparison view", () => {
    assert.equal(
      buildBilingualCompareHref("group-a", "ev-b"),
      "/evidence/detail?groupId=group-a&view=compare&evidenceId=ev-b",
    );
  });
});

describe("evidence document helpers", () => {
  it("synthesizes a full-document style reader from all trace snippets", () => {
    const document = buildEvidenceDocument(DETAIL, "original");

    assert.equal(document.paragraphs.length, 1);
    assert.equal(
      document.paragraphs[0].text,
      "The assay showed reduced DNA repair activity.",
    );
    assert.deepEqual(document.paragraphs[0].highlights.map((highlight) => ({
      tone: highlight.tone,
      start: highlight.start,
      end: highlight.end,
      evidenceId: highlight.evidenceId,
    })), [
      {
        tone: "functional",
        start: 17,
        end: 43,
        evidenceId: "ev-b",
      },
    ]);
  });

  it("filters highlight ranges by enabled evidence tones", () => {
    const document = buildEvidenceDocument(
      DETAIL,
      "original",
      new Set(["classification"]),
    );

    assert.equal(document.paragraphs.length, 1);
    assert.equal(document.paragraphs[0].highlights.length, 0);
  });

  it("counts evidence highlight categories from group items", () => {
    const counts = countEvidenceHighlightTones(DETAIL.items);

    assert.equal(counts.classification, 1);
    assert.equal(counts.functional, 1);
  });

  it("uses value fallback when snippet offsets have no marked range", () => {
    const detail: EvidenceGroupDetailResponse = {
      ...DETAIL,
      original_document_text: "Testing confirmed RB expression.",
      items: [{
        canonical_evidence_id: "ev-rb",
        field_id: "A.gene_symbol",
        category: "A",
        review_status: "provisional",
        value: "RB",
      }],
      traces: [{
        canonical_evidence_id: "ev-rb",
        field_id: "A.gene_symbol",
        field_name: "Gene symbol",
        original_value: "RB",
        translated_value: null,
        alignment_confidence: null,
        original: {
          text: "Testing confirmed RB expression.",
          highlight_start: 0,
          highlight_end: 0,
          source_span: {},
        },
        translated: null,
      }],
    };

    const document = buildEvidenceDocument(detail, "original");

    assert.deepEqual(document.paragraphs[0].highlights.map((highlight) => ({
      start: highlight.start,
      end: highlight.end,
      tone: highlight.tone,
    })), [{
      start: 18,
      end: 20,
      tone: "gene",
    }]);
  });
});
