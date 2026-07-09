import { useLayoutEffect, useState } from "react";
import type { RefObject } from "react";
import type { UserAnnotation } from "../../types/annotations";
import type { OverlayRect } from "./contracts";
import { computeAnnotationOverlays } from "./geometry";

export function useAnnotationOverlays(
  containerRef: RefObject<HTMLDivElement | null>,
  annotations: UserAnnotation[],
  recomputeDeps: unknown[],
): OverlayRect[] {
  const [overlays, setOverlays] = useState<OverlayRect[]>([]);

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const recompute = () => {
      if (annotations.length === 0) {
        setOverlays([]);
        return;
      }
      setOverlays(computeAnnotationOverlays(el, annotations));
    };

    recompute();

    if (typeof ResizeObserver === "undefined") return;
    const resizeObserver = new ResizeObserver(recompute);
    resizeObserver.observe(el);
    return () => resizeObserver.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [containerRef, annotations, ...recomputeDeps]);

  return overlays;
}
