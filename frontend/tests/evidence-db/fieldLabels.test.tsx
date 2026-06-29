import { describe, expect, it } from "vitest";

import {
  EVIDENCE_DB_LABELS,
  formatConfidencePercent,
  formatCoverageCount,
  formatReviewedCount,
} from "../../src/features/evidence-db/utils/fieldLabels";

describe("fieldLabels", () => {
  it("formats confidence ratios as rounded percentages", () => {
    expect(formatConfidencePercent(0.844)).toBe("84%");
    expect(formatConfidencePercent(null)).toBe("—");
    expect(formatConfidencePercent(undefined)).toBe("—");
  });

  it("formats review progress counts", () => {
    expect(formatReviewedCount({ reviewed: 3, total: 5 })).toBe("Reviewed 3/5");
  });

  it("formats coverage counts", () => {
    expect(formatCoverageCount({ coveredCategories: 4, totalCategories: 10 })).toBe("4/10");
  });

  it("centralizes repeated evidence DB labels", () => {
    expect(EVIDENCE_DB_LABELS.reviewProgress).toBe("Review progress");
    expect(EVIDENCE_DB_LABELS.exportReport).toBe("Export report");
  });
});
