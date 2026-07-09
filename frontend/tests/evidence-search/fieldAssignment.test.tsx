import { describe, expect, it } from "vitest";

import { EVIDENCE_FIELD_SPECS } from "../../src/lib/constants/evidenceFields";
import type { EvidenceGroupItem } from "../../src/features/evidence-search/types/evidenceSearch";
import {
  applyFieldAssignmentToDetail,
  applyReviewStatusToDetail,
  buildAssignableFieldTypes,
  buildFieldAssignmentPatch,
  cardFieldForFieldId,
} from "../../src/features/evidence-search/utils/fieldAssignment";

function item(overrides: Partial<EvidenceGroupItem>): EvidenceGroupItem {
  return {
    canonical_evidence_id: overrides.canonical_evidence_id ?? "evidence-1",
    field_id: overrides.field_id ?? "A.gene_symbol",
    field_name: overrides.field_name ?? "Gene symbol",
    category: overrides.category ?? "A",
    value: overrides.value ?? "BRCA1",
    review_status: overrides.review_status ?? "provisional",
    confidence: overrides.confidence ?? 0.9,
    track: overrides.track ?? "original",
    page: overrides.page ?? 1,
  };
}

describe("field assignment projection", () => {
  it("maps supported catalog field ids to backend card fields", () => {
    expect(cardFieldForFieldId("A.gene_symbol")).toBe("gene");
    expect(cardFieldForFieldId("A.variant_hgvs_c")).toBe("variant");
    expect(cardFieldForFieldId("A.variant_legacy_name")).toBe("variant");
    expect(cardFieldForFieldId("B.disease_diagnosis")).toBe("disease");
    expect(cardFieldForFieldId("B.sex")).toBeNull();
  });

  it("only exposes current group fields that can be patched", () => {
    const options = buildAssignableFieldTypes(
      [
        item({ field_id: "A.gene_symbol", field_name: "Gene symbol" }),
        item({
          canonical_evidence_id: "evidence-2",
          field_id: "B.sex",
          field_name: "Sex",
          category: "B",
        }),
      ],
      EVIDENCE_FIELD_SPECS,
    );

    expect(options.map((option) => option.fieldId)).toEqual(["A.gene_symbol"]);
  });

  it("builds a patch body accepted by the evidence feedback API", () => {
    const patch = buildFieldAssignmentPatch(
      [item({ canonical_evidence_id: "evidence-1", field_id: "A.gene_symbol" })],
      "BRCA1",
      "A.gene_symbol",
    );

    expect(patch).toEqual({
      canonicalEvidenceId: "evidence-1",
      cardField: "gene",
      body: {
        fields: { gene: "BRCA1" },
        change_reason: "Text selection assignment to A.gene_symbol",
      },
    });
  });

  it("applies a confirmed assignment to the visible group detail", () => {
    const assignment = buildFieldAssignmentPatch(
      [item({ canonical_evidence_id: "evidence-1", field_id: "A.gene_symbol" })],
      "TP53",
      "A.gene_symbol",
    );
    expect(assignment).not.toBeNull();

    const detail = {
      group_id: "group-1",
      source_document_id: "source-1",
      title: "Evidence paper",
      gene: "BRCA1",
      variant: null,
      disease: null,
      classification: null,
      item_count: 1,
      distribution: {
        by_category: { A: 1 },
        by_field: { "A.gene_symbol": 1 },
        by_status: { provisional: 1 },
        by_track: { original: 1 },
      },
      items: [item({ canonical_evidence_id: "evidence-1", field_id: "A.gene_symbol" })],
      traces: [],
    };

    const updated = applyFieldAssignmentToDetail(
      detail,
      assignment!,
      "TP53",
      "corrected",
    );

    expect(updated?.gene).toBe("TP53");
    expect(updated?.items[0]).toMatchObject({
      value: "TP53",
      review_status: "corrected",
    });
    expect(updated?.distribution.by_status).toEqual({ corrected: 1 });
  });

  it("applies a confirmed review status to the visible group detail", () => {
    const detail = {
      group_id: "group-1",
      source_document_id: "source-1",
      title: "Evidence paper",
      gene: "BRCA1",
      variant: null,
      disease: null,
      classification: null,
      item_count: 2,
      distribution: {
        by_category: { A: 2 },
        by_field: { "A.gene_symbol": 2 },
        by_status: { provisional: 2 },
        by_track: { original: 2 },
      },
      items: [
        item({ canonical_evidence_id: "evidence-1", review_status: "provisional" }),
        item({ canonical_evidence_id: "evidence-2", review_status: "provisional" }),
      ],
      traces: [],
    };

    const updated = applyReviewStatusToDetail(detail, "evidence-1", "approved");

    expect(updated?.items).toEqual([
      expect.objectContaining({
        canonical_evidence_id: "evidence-1",
        review_status: "approved",
      }),
      expect.objectContaining({
        canonical_evidence_id: "evidence-2",
        review_status: "provisional",
      }),
    ]);
    expect(updated?.distribution.by_status).toEqual({
      provisional: 1,
      approved: 1,
    });
  });
});
