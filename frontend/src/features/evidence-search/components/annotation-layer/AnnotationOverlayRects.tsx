import { useMemo } from "react";
import { useI18n } from "@/lib/i18n";
import {
  DEFAULT_ANNOTATION_COLOR,
  type UserAnnotation,
} from "../../types/annotations";
import type { OverlayRect } from "./contracts";

interface AnnotationOverlayRectsProps {
  overlays: OverlayRect[];
  annotations: UserAnnotation[];
  onActivate: (annotationId: string) => void;
}

export function AnnotationOverlayRects({
  overlays,
  annotations,
  onActivate,
}: AnnotationOverlayRectsProps) {
  const { t } = useI18n();
  const annotationsById = useMemo(
    () => new Map(annotations.map((annotation) => [annotation.id, annotation])),
    [annotations],
  );

  return (
    <>
      {overlays.map((overlay) => {
        const annotation = annotationsById.get(overlay.id);
        if (!annotation) return null;
        const color = annotation.color ?? DEFAULT_ANNOTATION_COLOR;
        return (
          <div
            key={`${overlay.id}-${overlay.top}-${overlay.left}`}
            onClick={(event) => {
              event.stopPropagation();
              onActivate(annotation.id);
            }}
            style={{
              position: "absolute",
              top: overlay.top,
              left: overlay.left,
              width: overlay.width,
              height: overlay.height,
              backgroundColor: `${color}55`,
              borderBottom: `2px solid ${color}`,
              cursor: "pointer",
              borderRadius: 2,
            }}
            aria-label={annotation.note ? t("annotation.label", { note: annotation.note }) : t("annotation.user")}
          />
        );
      })}
    </>
  );
}
