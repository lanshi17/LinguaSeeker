import { useEffect, useState } from "react";
import type { RefObject } from "react";
import type { SelectionInfo } from "./contracts";
import { selectionInContainer } from "./geometry";

interface UseAnnotationSelectionParams {
  containerRef: RefObject<HTMLDivElement | null>;
  popupRef: RefObject<HTMLDivElement>;
  enabled: boolean;
}

export function useAnnotationSelection({
  containerRef,
  popupRef,
  enabled,
}: UseAnnotationSelectionParams): {
  selection: SelectionInfo | null;
  setSelection: (selection: SelectionInfo | null) => void;
  clearSelection: () => void;
} {
  const [selection, setSelection] = useState<SelectionInfo | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const el = containerRef.current;
    if (!el) return;
    const handleMouseUp = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (popupRef.current?.contains(target)) return;
      if (target.closest?.(".ant-select-dropdown")) return;
      if (target.closest?.("[data-reviewable]")) return;
      requestAnimationFrame(() => {
        setSelection(selectionInContainer(el));
      });
    };
    document.addEventListener("mouseup", handleMouseUp);
    return () => document.removeEventListener("mouseup", handleMouseUp);
  }, [containerRef, enabled, popupRef]);

  const clearSelection = () => {
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  };

  return { selection, setSelection, clearSelection };
}
