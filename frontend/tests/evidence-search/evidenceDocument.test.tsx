import { describe, expect, it } from "vitest";

import { buildEvidenceDocument } from "../../src/features/evidence-search/utils/evidenceDocument";
import type { EvidenceGroupDetailResponse } from "../../src/features/evidence-search/types/evidenceSearch";

function makeDetail(): EvidenceGroupDetailResponse {
  return {
    group_id: "group-a",
    source_document_id: "doc-1",
    title: "Functional evidence paper",
    pmid: null,
    doi: null,
    gene: "GENE1",
    variant: "c.1A>G",
    disease: "Example syndrome",
    classification: "pathogenic",
    item_count: 1,
    avg_confidence: 0.9,
    distribution: {
      by_category: {},
      by_field: {},
      by_status: {},
      by_track: {},
    },
    items: [{
      canonical_evidence_id: "ev-functional",
      field_id: "F.functional_assay",
      category: "F",
      review_status: "provisional",
      value: "abnormal functional assay",
    }],
    traces: [{
      canonical_evidence_id: "ev-functional",
      field_id: "F.functional_assay",
      field_name: "Functional assay",
      original_value: "abnormal functional assay",
      translated_value: null,
      alignment_confidence: null,
      original: {
        text: "Functional testing showed a loss of kinase activity in patient cells.",
        highlight_start: 28,
        highlight_end: 51,
        source_span: { sentence_index: 1 },
      },
      translated: null,
    }],
  };
}

describe("buildEvidenceDocument", () => {
  it("matches non-English text across accents and hyphen variants", () => {
    const detail: EvidenceGroupDetailResponse = {
      ...makeDetail(),
      original_document_text: "The patient was diagnosed with Birt–Hogg–Dubé syndrome.",
      items: [{
        canonical_evidence_id: "ev-disease",
        field_id: "B.disease_name",
        category: "B",
        review_status: "provisional",
        value: "Birt-Hogg-Dube syndrome",
      }],
      traces: [],
    };

    const document = buildEvidenceDocument(detail, "original");

    expect(document.paragraphs[0].highlights.map((highlight) => ({
      text: document.paragraphs[0].text.slice(highlight.start, highlight.end),
      tone: highlight.tone,
      evidenceId: highlight.evidenceId,
    }))).toEqual([{
      text: "Birt–Hogg–Dubé syndrome",
      tone: "disease",
      evidenceId: "ev-disease",
    }]);
  });

  it("matches trace sentences across full-width characters and CJK punctuation", () => {
    const detail: EvidenceGroupDetailResponse = {
      ...makeDetail(),
      original_document_text: "背景。患者携带Ｃ．１２３Ａ＞Ｇ变异。讨论。",
      items: [{
        canonical_evidence_id: "ev-variant",
        field_id: "A.variant_hgvs",
        category: "A",
        review_status: "provisional",
        value: "not present as written",
      }],
      traces: [{
        canonical_evidence_id: "ev-variant",
        field_id: "A.variant_hgvs",
        field_name: "Variant HGVS",
        original_value: "c.123A>G",
        translated_value: null,
        alignment_confidence: null,
        original: {
          text: "患者携带c.123A>G变异.",
          highlight_start: 4,
          highlight_end: 12,
          source_span: { sentence_index: 1 },
        },
        translated: null,
      }],
    };

    const document = buildEvidenceDocument(detail, "original");

    expect(document.paragraphs[0].highlights.map((highlight) => ({
      text: document.paragraphs[0].text.slice(highlight.start, highlight.end),
      tone: highlight.tone,
      evidenceId: highlight.evidenceId,
    }))).toEqual([{
      text: "Ｃ．１２３Ａ＞Ｇ",
      tone: "variant",
      evidenceId: "ev-variant",
    }]);
  });

  it("uses trace sentence spans in full text when value search misses", () => {
    const detail = {
      ...makeDetail(),
      original_document_text:
        "Introduction. Functional testing showed a loss of kinase activity in patient cells. Discussion.",
    };

    const document = buildEvidenceDocument(detail, "original");

    expect(document.paragraphs[0].highlights.map((highlight) => ({
      start: highlight.start,
      end: highlight.end,
      tone: highlight.tone,
      evidenceId: highlight.evidenceId,
    }))).toEqual([{
      start: 42,
      end: 65,
      tone: "functional",
      evidenceId: "ev-functional",
    }]);
  });

  it("maps trace sentence spans through whitespace differences in full text", () => {
    const detail = {
      ...makeDetail(),
      original_document_text:
        "Introduction. Functional testing showed a loss of\nkinase   activity in patient cells. Discussion.",
    };

    const document = buildEvidenceDocument(detail, "original");

    expect(document.paragraphs[0].highlights.map((highlight) => ({
      text: document.paragraphs[0].text.slice(highlight.start, highlight.end),
      tone: highlight.tone,
      evidenceId: highlight.evidenceId,
    }))).toEqual([{
      text: "loss of\nkinase   activity",
      tone: "functional",
      evidenceId: "ev-functional",
    }]);
  });
});
