import { useCallback, useState } from "react";

export const EVIDENCE_DB_VIEW_PREFS_KEY = "lingua:evidence-db:view-prefs";

export interface EvidenceDbViewPrefs {
  showUpdated: boolean;
  showCategories: boolean;
  showReviewProgress: boolean;
  showPmid: boolean;
  showFieldCount: boolean;
  showSourceLanguage: boolean;
}

export const DEFAULT_EVIDENCE_DB_VIEW_PREFS: EvidenceDbViewPrefs = {
  showUpdated: true,
  showCategories: true,
  showReviewProgress: true,
  showPmid: true,
  showFieldCount: true,
  showSourceLanguage: true,
};

function normalizePrefs(value: unknown): EvidenceDbViewPrefs {
  if (!value || typeof value !== "object") {
    return DEFAULT_EVIDENCE_DB_VIEW_PREFS;
  }
  const candidate = value as Partial<Record<keyof EvidenceDbViewPrefs, unknown>>;
  return {
    showUpdated:
      typeof candidate.showUpdated === "boolean"
        ? candidate.showUpdated
        : DEFAULT_EVIDENCE_DB_VIEW_PREFS.showUpdated,
    showCategories:
      typeof candidate.showCategories === "boolean"
        ? candidate.showCategories
        : DEFAULT_EVIDENCE_DB_VIEW_PREFS.showCategories,
    showReviewProgress:
      typeof candidate.showReviewProgress === "boolean"
        ? candidate.showReviewProgress
        : DEFAULT_EVIDENCE_DB_VIEW_PREFS.showReviewProgress,
    showPmid:
      typeof candidate.showPmid === "boolean"
        ? candidate.showPmid
        : DEFAULT_EVIDENCE_DB_VIEW_PREFS.showPmid,
    showFieldCount:
      typeof candidate.showFieldCount === "boolean"
        ? candidate.showFieldCount
        : DEFAULT_EVIDENCE_DB_VIEW_PREFS.showFieldCount,
    showSourceLanguage:
      typeof candidate.showSourceLanguage === "boolean"
        ? candidate.showSourceLanguage
        : DEFAULT_EVIDENCE_DB_VIEW_PREFS.showSourceLanguage,
  };
}

function loadPrefs(): EvidenceDbViewPrefs {
  try {
    const raw = window.localStorage.getItem(EVIDENCE_DB_VIEW_PREFS_KEY);
    if (!raw) return DEFAULT_EVIDENCE_DB_VIEW_PREFS;
    return normalizePrefs(JSON.parse(raw));
  } catch {
    return DEFAULT_EVIDENCE_DB_VIEW_PREFS;
  }
}

function savePrefs(prefs: EvidenceDbViewPrefs): void {
  try {
    window.localStorage.setItem(EVIDENCE_DB_VIEW_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // Ignore storage failures; preferences are an enhancement.
  }
}

export function useEvidenceDbViewPrefs() {
  const [prefs, setPrefs] = useState<EvidenceDbViewPrefs>(() => loadPrefs());

  const setPreference = useCallback(
    <K extends keyof EvidenceDbViewPrefs>(key: K, value: EvidenceDbViewPrefs[K]) => {
      setPrefs((prev) => {
        const next = { ...prev, [key]: value };
        savePrefs(next);
        return next;
      });
    },
    [],
  );

  return {
    prefs,
    setPreference,
  };
}
