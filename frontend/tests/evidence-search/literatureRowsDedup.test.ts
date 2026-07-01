import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildLiteratureRows } from "../../src/features/evidence-search/utils/literatureRows";
import type { EvidenceSearchResult } from "../../src/features/evidence-search/types/evidenceSearch";

describe("buildLiteratureRows duplicate literature handling", () => {
  it("merges duplicate literature rows across different source documents", () => {
    const results: EvidenceSearchResult[] = [
      {
        group_id: "group-duplicate-a",
        source_document_id: "doc-duplicate-a",
        title: "Shared ACMG literature",
        pmid: "98765432",
        doi: "10.1000/shared",
        gene: "BRCA1",
        variant: "c.1A>G",
        disease: "Breast cancer",
        classification: "pathogenic",
        field_count: 4,
        avg_confidence: 0.9,
        review_status: "approved",
      },
      {
        group_id: "group-duplicate-b",
        source_document_id: "doc-duplicate-b",
        title: "Shared ACMG literature",
        pmid: "98765432",
        doi: "https://doi.org/10.1000/SHARED",
        gene: "BRCA2",
        variant: "c.2A>G",
        disease: "Ovarian cancer",
        classification: "likely pathogenic",
        field_count: 6,
        avg_confidence: 0.8,
        review_status: "provisional",
      },
    ];

    const rows = buildLiteratureRows(results);

    assert.equal(rows.length, 1);
    assert.equal(rows[0].documentId, "doc-duplicate-a");
    assert.equal(rows[0].representativeGroupId, "group-duplicate-a");
    assert.equal(rows[0].fieldCount, 10);
    assert.equal(rows[0].groupCount, 2);
    assert.equal(rows[0].reviewStatus, "mixed");
    assert.deepEqual(rows[0].genes, ["BRCA1", "BRCA2"]);
    assert.deepEqual(rows[0].variants, ["c.1A>G", "c.2A>G"]);
  });
});
