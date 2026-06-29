import { describe, expect, it } from "vitest";

import {
  aggregateVariants,
  buildVariantGroupDocumentPairs,
  filterAndPaginateVariants,
  parseVariantSlug,
} from "../../src/features/evidence-db/utils/variantAggregation";
import type { EvidenceSearchResult } from "../../src/features/evidence-search/types/evidenceSearch";

const JOINED_VARIANT = "c.316C>T; c.502C>T; c.808C>T; c.913insT; c.1126C>T";
const JOINED_GROUP_ID = `gene=MECP2|variant=${JOINED_VARIANT}`;

function makeResult(overrides: Partial<EvidenceSearchResult> = {}): EvidenceSearchResult {
  return {
    group_id: "gene=MECP2|variant=c.316C>T",
    source_document_id: "doc-1",
    gene: "MECP2",
    variant: "c.316C>T",
    disease: "Rett syndrome",
    classification: "Pathogenic",
    field_count: 10,
    avg_confidence: 0.9,
    review_status: "provisional",
    canonical_evidence_id: "ev-1",
    ...overrides,
  };
}

describe("aggregateVariants — one row per variant site", () => {
  it("keeps a single-variant result as one row", () => {
    const entries = aggregateVariants([makeResult()]);
    expect(entries).toHaveLength(1);
    expect(entries[0].variant).toBe("c.316C>T");
    expect(entries[0].gene).toBe("MECP2");
  });

  it("splits the MECP2 multi-variant result into five rows", () => {
    const entries = aggregateVariants([
      makeResult({ variant: JOINED_VARIANT, group_id: JOINED_GROUP_ID }),
    ]);
    expect(entries).toHaveLength(5);
    expect(entries.map((e) => e.variant).sort()).toEqual(
      ["c.1126C>T", "c.316C>T", "c.502C>T", "c.808C>T", "c.913insT"],
    );
    // Each split row inherits the group's gene and classification.
    for (const e of entries) {
      expect(e.gene).toBe("MECP2");
      expect(e.classificationLevel).toBe("pathogenic");
      // All split rows share the original group_id so L2 detail resolves.
      expect(e.groupIds).toEqual([JOINED_GROUP_ID]);
    }
  });

  it("does not split a variant without a semicolon", () => {
    const entries = aggregateVariants([makeResult({ variant: "c.316C>T" })]);
    expect(entries).toHaveLength(1);
  });

  it("aggregates a shared split variant from different groups", () => {
    const entries = aggregateVariants([
      makeResult({
        variant: "c.316C>T; c.502C>T",
        group_id: "gene=MECP2|variant=c.316C>T; c.502C>T",
        source_document_id: "doc-a",
      }),
      makeResult({
        variant: "c.316C>T; c.808C>T",
        group_id: "gene=MECP2|variant=c.316C>T; c.808C>T",
        source_document_id: "doc-b",
      }),
    ]);
    const c316 = entries.find((e) => e.variant === "c.316C>T");
    expect(c316).toBeDefined();
    expect(c316!.evidenceGroupCount).toBe(2);
    expect(c316!.groupIds).toHaveLength(2);
    expect(c316!.sourceDocumentIds).toHaveLength(2);
  });
});

describe("filterAndPaginateVariants — stats not inflated by split rows", () => {
  it("counts distinct evidence groups and literature, not per-row sums", () => {
    const entries = aggregateVariants([
      makeResult({ variant: JOINED_VARIANT, group_id: JOINED_GROUP_ID }),
    ]);
    const data = filterAndPaginateVariants(entries, { page: 1, pageSize: 50 });
    // Five variant rows, but only one underlying evidence group and document.
    expect(data.stats.totalVariants).toBe(5);
    expect(data.stats.totalEvidenceGroups).toBe(1);
    expect(data.stats.totalLiterature).toBe(1);
  });

  it("filters by an individual split variant", () => {
    const entries = aggregateVariants([
      makeResult({ variant: JOINED_VARIANT, group_id: JOINED_GROUP_ID }),
    ]);
    const data = filterAndPaginateVariants(entries, {
      page: 1,
      pageSize: 50,
      variant: "c.502C>T",
    });
    expect(data.items).toHaveLength(1);
    expect(data.items[0].variant).toBe("c.502C>T");
    expect(data.total).toBe(1);
  });
});

describe("variant detail query helpers", () => {
  it("parses a variant slug into evidence search filters", () => {
    expect(parseVariantSlug("FLCN:c.1177-5_-3delCTC:Birt-Hogg-Dube syndrome")).toEqual({
      gene: "FLCN",
      variant: "c.1177-5_-3delCTC",
      disease: "Birt-Hogg-Dube syndrome",
    });
  });

  it("builds concrete group/document pairs without a Cartesian product", () => {
    const rows = [
      makeResult({
        group_id: "group-a",
        source_document_id: "doc-1",
        gene: "FLCN",
        variant: "c.1177-5_-3delCTC",
        disease: "Birt-Hogg-Dube syndrome",
      }),
      makeResult({
        group_id: "group-b",
        source_document_id: "doc-2",
        gene: "FLCN",
        variant: "c.1177-5_-3delCTC",
        disease: "Birt-Hogg-Dube syndrome",
      }),
    ];

    expect(
      buildVariantGroupDocumentPairs(
        rows,
        "FLCN:c.1177-5_-3delCTC:Birt-Hogg-Dube syndrome",
      ),
    ).toEqual([
      { groupId: "group-a", sourceDocumentId: "doc-1" },
      { groupId: "group-b", sourceDocumentId: "doc-2" },
    ]);
  });
});
