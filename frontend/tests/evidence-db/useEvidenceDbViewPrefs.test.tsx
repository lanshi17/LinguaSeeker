import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import {
  EVIDENCE_DB_VIEW_PREFS_KEY,
  useEvidenceDbViewPrefs,
} from "../../src/features/evidence-db/hooks/useEvidenceDbViewPrefs";

describe("useEvidenceDbViewPrefs", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("uses the compact default field set", () => {
    const { result } = renderHook(() => useEvidenceDbViewPrefs());

    expect(result.current.prefs).toEqual({
      showUpdated: true,
      showCategories: true,
      showReviewProgress: true,
      showPmid: true,
      showFieldCount: true,
      showSourceLanguage: true,
    });
  });

  it("persists display preference toggles", () => {
    const { result, rerender } = renderHook(() => useEvidenceDbViewPrefs());

    act(() => {
      result.current.setPreference("showUpdated", false);
      result.current.setPreference("showReviewProgress", false);
    });
    rerender();

    expect(result.current.prefs.showUpdated).toBe(false);
    expect(result.current.prefs.showReviewProgress).toBe(false);
    expect(JSON.parse(window.localStorage.getItem(EVIDENCE_DB_VIEW_PREFS_KEY) ?? "{}")).toEqual({
      showUpdated: false,
      showCategories: true,
      showReviewProgress: false,
      showPmid: true,
      showFieldCount: true,
      showSourceLanguage: true,
    });
  });

  it("falls back to defaults for invalid stored data", () => {
    window.localStorage.setItem(EVIDENCE_DB_VIEW_PREFS_KEY, "{bad json");

    const { result } = renderHook(() => useEvidenceDbViewPrefs());

    expect(result.current.prefs.showUpdated).toBe(true);
    expect(result.current.prefs.showCategories).toBe(true);
    expect(result.current.prefs.showReviewProgress).toBe(true);
  });
});
