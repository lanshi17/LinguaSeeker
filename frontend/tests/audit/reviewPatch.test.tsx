import { describe, expect, it } from "vitest";

import { buildReviewPatchOperations } from "@/features/audit/utils/reviewPatch";
import type { EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";

function item(overrides: Partial<EvidenceGroupItem>): EvidenceGroupItem {
  return {
    canonical_evidence_id: "00000000-0000-0000-0000-000000000001",
    field_id: "A.gene_symbol",
    field_name: "Gene symbol",
    value: "GLA",
    review_status: "provisional",
    ...overrides,
  };
}

describe("buildReviewPatchOperations", () => {
  it("maps field-level edits to backend card fields", () => {
    const operations = buildReviewPatchOperations({
      items: [
        item({
          canonical_evidence_id: "00000000-0000-0000-0000-000000000001",
          field_id: "A.gene_symbol",
          field_name: "Gene symbol",
          value: "GLA",
        }),
        item({
          canonical_evidence_id: "00000000-0000-0000-0000-000000000002",
          field_id: "B.disease_diagnosis",
          field_name: "Disease diagnosis",
          value: "Fabry disease",
        }),
      ],
      editedFields: {
        "A.gene_symbol": "PRKN",
        "B.disease_diagnosis": "Parkinson disease",
      },
      newStatus: "corrected",
      changeReason: "Curator correction",
    });

    expect(operations).toEqual([
      {
        canonicalEvidenceId: "00000000-0000-0000-0000-000000000001",
        body: {
          fields: { gene: "PRKN" },
          change_reason: "Curator correction",
          new_status: "corrected",
        },
      },
      {
        canonicalEvidenceId: "00000000-0000-0000-0000-000000000002",
        body: {
          fields: { disease: "Parkinson disease" },
          change_reason: "Curator correction",
          new_status: "corrected",
        },
      },
    ]);
  });

  it("creates status-only operations for unchanged or unmapped fields", () => {
    const operations = buildReviewPatchOperations({
      items: [
        item({
          canonical_evidence_id: "00000000-0000-0000-0000-000000000003",
          field_id: "Z.unmapped_field",
          field_name: "Unmapped field",
          value: "Original",
        }),
      ],
      editedFields: {
        "Z.unmapped_field": "Edited",
      },
      newStatus: "approved",
      changeReason: "",
    });

    expect(operations).toEqual([
      {
        canonicalEvidenceId: "00000000-0000-0000-0000-000000000003",
        body: {
          fields: {},
          new_status: "approved",
        },
      },
    ]);
  });
});
