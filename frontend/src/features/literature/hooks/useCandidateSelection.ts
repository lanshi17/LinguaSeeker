"use client";

import { useState, useCallback } from "react";

const MAX_SELECTION = 10;

/**
 * Manages candidate selection state (checkbox toggle, max limit).
 */
export function useCandidateSelection() {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < MAX_SELECTION) {
        next.add(id);
      }
      return next;
    });
  }, []);

  const clear = useCallback(() => setSelectedIds(new Set()), []);

  return {
    selectedIds,
    selectedCount: selectedIds.size,
    isSelected: (id: string) => selectedIds.has(id),
    toggle,
    clear,
    isAtLimit: selectedIds.size >= MAX_SELECTION,
  };
}
