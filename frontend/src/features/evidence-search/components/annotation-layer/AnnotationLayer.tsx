/**
 * Shared user-annotation layer for document paragraphs.
 *
 * Renders translucent overlay rectangles over annotation spans anchored to the
 * paragraph's flattened visible text, a selection popover to create new
 * annotations, and an edit popover for note/color/delete.
 */
import { useMemo, useRef, useState } from "react";
import { Popover } from "antd";
import { useI18n } from "@/lib/i18n";
import { AnnotationEditor } from "./AnnotationEditor";
import { AnnotationOverlayRects } from "./AnnotationOverlayRects";
import { AnnotationSelectionToolbar } from "./AnnotationSelectionToolbar";
import type { AnnotationLayerProps } from "./contracts";
import { useAnnotationOverlays } from "./useAnnotationOverlays";
import { useAnnotationSelection } from "./useAnnotationSelection";

export function AnnotationLayer({
  containerRef,
  paragraphId,
  track,
  annotations,
  recomputeDeps = [],
  onCreateAnnotation,
  onUpdateAnnotation,
  onDeleteAnnotation,
  onAssignField,
  fieldTypes = [],
}: AnnotationLayerProps) {
  const { t } = useI18n();
  const overlays = useAnnotationOverlays(containerRef, annotations, recomputeDeps);
  const popupRef = useRef<HTMLDivElement>(null);
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | null>(null);
  const [creatingColor, setCreatingColor] = useState<string | null>(null);
  const [assigningField, setAssigningField] = useState(false);
  const { selection, clearSelection } = useAnnotationSelection({
    containerRef,
    popupRef,
    enabled: Boolean(onCreateAnnotation || onAssignField),
  });

  const activeAnnotation = useMemo(
    () => (
      activeAnnotationId
        ? annotations.find((annotation) => annotation.id === activeAnnotationId) ?? null
        : null
    ),
    [activeAnnotationId, annotations],
  );

  const handleCreate = (color: string) => {
    if (!selection || !onCreateAnnotation || creatingColor) return;
    setCreatingColor(color);
    Promise.resolve(onCreateAnnotation({
      paragraph_id: paragraphId,
      track,
      start_offset: selection.start_offset,
      end_offset: selection.end_offset,
      color,
    }))
      .then(clearSelection)
      .catch(() => undefined)
      .finally(() => setCreatingColor(null));
  };

  const handleAssignField = (fieldType: string) => {
    if (!selection || !onAssignField || assigningField) return;
    setAssigningField(true);
    Promise.resolve(onAssignField(selection.selectedText, fieldType))
      .then(clearSelection)
      .catch(() => undefined)
      .finally(() => setAssigningField(false));
  };

  return (
    <>
      <AnnotationOverlayRects
        overlays={overlays}
        annotations={annotations}
        onActivate={setActiveAnnotationId}
      />

      {selection && (onCreateAnnotation || onAssignField) && (
        <AnnotationSelectionToolbar
          selection={selection}
          popupRef={popupRef}
          canCreate={Boolean(onCreateAnnotation)}
          canAssignField={Boolean(onAssignField)}
          creatingColor={creatingColor}
          assigningField={assigningField}
          fieldTypes={fieldTypes}
          onCreate={handleCreate}
          onAssignField={handleAssignField}
        />
      )}

      <Popover
        open={activeAnnotation != null}
        onOpenChange={(open) => {
          if (!open) setActiveAnnotationId(null);
        }}
        trigger="click"
        title={t("annotation.edit")}
        content={
          activeAnnotation ? (
            <AnnotationEditor
              annotation={activeAnnotation}
              onUpdate={onUpdateAnnotation}
              onDelete={onDeleteAnnotation}
              onDone={() => setActiveAnnotationId(null)}
            />
          ) : null
        }
        placement="right"
      >
        <span style={{ display: "none" }} />
      </Popover>
    </>
  );
}
