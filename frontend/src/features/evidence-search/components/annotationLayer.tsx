/**
 * Shared user-annotation layer for document paragraphs.
 *
 * Renders translucent overlay rectangles over annotation spans (anchored to
 * the paragraph's flattened visible text), a selection popover to create new
 * annotations, and an edit popover for note/color/delete.
 *
 * Coordinate system: offsets are into the paragraph container's visible text
 * (flattened textContent of all descendant text nodes). The layer is visually
 * and structurally decoupled from evidence-highlight DOM wrapping — overlays
 * are absolutely positioned divs, so they never conflict with `<mark>` splits.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Input, Button, Popover, Tooltip, Select, message } from "antd";
import { useI18n } from "@/lib/i18n";
import { DeleteOutlined } from "@ant-design/icons";
import {
  ANNOTATION_COLORS,
  DEFAULT_ANNOTATION_COLOR,
  type AnnotationTrack,
  type UserAnnotation,
} from "../types/annotations";
import { CATEGORY_COLORS } from "../utils/evidenceDocument";

interface TextNodeOffset {
  node: Text;
  start: number;
}

function collectTextNodeOffsets(container: HTMLElement): TextNodeOffset[] {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
  const offsets: TextNodeOffset[] = [];
  let acc = 0;
  let walkNode: Text | null;
  while ((walkNode = walker.nextNode() as Text | null)) {
    const content = walkNode.textContent ?? "";
    if (!content) continue;
    offsets.push({ node: walkNode, start: acc });
    acc += content.length;
  }
  return offsets;
}

function offsetToPoint(
  offsets: TextNodeOffset[],
  offset: number,
): { node: Text; localOffset: number } | null {
  if (offsets.length === 0) return null;
  for (const { node, start } of offsets) {
    const len = node.textContent?.length ?? 0;
    if (offset <= start + len) {
      return { node, localOffset: Math.max(0, Math.min(len, offset - start)) };
    }
  }
  const last = offsets[offsets.length - 1];
  return { node: last.node, localOffset: last.node.textContent?.length ?? 0 };
}

interface OverlayRect {
  id: string;
  top: number;
  left: number;
  width: number;
  height: number;
}

function computeAnnotationOverlays(
  container: HTMLElement,
  annotations: UserAnnotation[],
): OverlayRect[] {
  const offsets = collectTextNodeOffsets(container);
  const containerRect = container.getBoundingClientRect();
  const overlays: OverlayRect[] = [];

  for (const ann of annotations) {
    const startPt = offsetToPoint(offsets, ann.start_offset);
    const endPt = offsetToPoint(offsets, ann.end_offset);
    if (!startPt || !endPt) continue;

    const range = document.createRange();
    try {
      range.setStart(startPt.node, startPt.localOffset);
      range.setEnd(endPt.node, endPt.localOffset);
    } catch {
      continue;
    }

    for (const rect of range.getClientRects()) {
      if (rect.width < 1 || rect.height < 1) continue;
      overlays.push({
        id: ann.id,
        top: rect.top - containerRect.top + container.scrollTop,
        left: rect.left - containerRect.left + container.scrollLeft,
        width: rect.width,
        height: rect.height,
      });
    }
  }
  return overlays;
}

interface SelectionInfo {
  start_offset: number;
  end_offset: number;
  rect: DOMRect;
  selectedText: string;
}

function findPointForNode(
  offsets: TextNodeOffset[],
  node: Node,
  offset: number,
): number | null {
  if (node.nodeType === Node.TEXT_NODE) {
    const entry = offsets.find((o) => o.node === node);
    if (!entry) return null;
    return entry.start + Math.min(offset, node.textContent?.length ?? 0);
  }
  let acc = 0;
  const childNodes = node.childNodes;
  for (let i = 0; i < Math.min(offset, childNodes.length); i++) {
    const child = childNodes[i];
    for (const { node: textNode, start } of offsets) {
      if (child.contains(textNode) || child === textNode) {
        acc = start + (textNode.textContent?.length ?? 0);
      }
    }
  }
  return acc;
}

function selectionInContainer(container: HTMLElement): SelectionInfo | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return null;
  const range = sel.getRangeAt(0);
  if (range.collapsed) return null;
  if (!container.contains(range.commonAncestorContainer)) return null;

  const offsets = collectTextNodeOffsets(container);
  const startPt = findPointForNode(offsets, range.startContainer, range.startOffset);
  const endPt = findPointForNode(offsets, range.endContainer, range.endOffset);
  if (startPt == null || endPt == null || endPt <= startPt) return null;
  return {
    start_offset: startPt,
    end_offset: endPt,
    rect: range.getBoundingClientRect(),
    selectedText: range.toString(),
  };
}

/** A field type option for the "Assign to field" dropdown. */
export interface FieldTypeOption {
  fieldId: string;
  label: string;
  category?: string | null;
}

export interface AnnotationLayerProps {
  /** Ref to the container whose visible text the annotations anchor to. */
  containerRef: React.RefObject<HTMLDivElement | null>;
  paragraphId: string;
  track: AnnotationTrack;
  annotations: UserAnnotation[];
  /** Dependency array trigger: recompute overlays when these change (e.g.
   *  markdown/highlights that reshape the DOM). */
  recomputeDeps?: unknown[];
  onCreateAnnotation?: (payload: {
    paragraph_id: string;
    track: AnnotationTrack;
    start_offset: number;
    end_offset: number;
    color: string;
  }) => void;
  onUpdateAnnotation?: (
    id: string,
    payload: { color?: string | null; note?: string | null },
  ) => void;
  onDeleteAnnotation?: (id: string) => void;
  /**
   * When provided, the text-selection popup shows a "Assign to field" button
   * alongside annotation colors. The callback receives the selected text and
   * the target field type chosen by the user.
   */
  onAssignField?: (selectedText: string, fieldType: string) => void;
  /** Available field types for the "Assign to field" dropdown. */
  fieldTypes?: FieldTypeOption[];
}

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
  const [overlays, setOverlays] = useState<OverlayRect[]>([]);
  const [selection, setSelection] = useState<SelectionInfo | null>(null);
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | null>(null);
  const popupRef = useRef<HTMLDivElement>(null);

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

    const ro = new ResizeObserver(recompute);
    ro.observe(el);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [annotations, ...recomputeDeps]);

  useEffect(() => {
    if (!onCreateAnnotation && !onAssignField) return;
    const el = containerRef.current;
    if (!el) return;
    const handleMouseUp = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      // Ignore clicks inside the selection popup, antd portals, or reviewable marks
      if (popupRef.current?.contains(target)) return;
      if (target.closest?.(".ant-select-dropdown")) return;
      if (target.closest?.("[data-reviewable]")) return;
      requestAnimationFrame(() => {
        setSelection(selectionInContainer(el));
      });
    };
    document.addEventListener("mouseup", handleMouseUp);
    return () => document.removeEventListener("mouseup", handleMouseUp);
  }, [containerRef, onCreateAnnotation, onAssignField]);

  const activeAnnotation = activeAnnotationId
    ? annotations.find((a) => a.id === activeAnnotationId) ?? null
    : null;

  const handleCreate = (color: string) => {
    if (!selection || !onCreateAnnotation) return;
    onCreateAnnotation({
      paragraph_id: paragraphId,
      track,
      start_offset: selection.start_offset,
      end_offset: selection.end_offset,
      color,
    });
    window.getSelection()?.removeAllRanges();
    setSelection(null);
    message.success(t("annotation.created"));
  };

  return (
    <>
      {overlays.map((ov) => {
        const ann = annotations.find((a) => a.id === ov.id);
        if (!ann) return null;
        const color = ann.color ?? DEFAULT_ANNOTATION_COLOR;
        return (
          <div
            key={`${ov.id}-${ov.top}-${ov.left}`}
            onClick={(e) => {
              e.stopPropagation();
              setActiveAnnotationId(ann.id);
            }}
            style={{
              position: "absolute",
              top: ov.top,
              left: ov.left,
              width: ov.width,
              height: ov.height,
              backgroundColor: color + "55",
              borderBottom: `2px solid ${color}`,
              cursor: "pointer",
              borderRadius: 2,
            }}
            aria-label={ann.note ? t("annotation.label", { note: ann.note }) : t("annotation.user")}
          />
        );
      })}

      {selection && (onCreateAnnotation || onAssignField) && (
        <div
          ref={popupRef}
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            position: "fixed",
            top: Math.max(8, selection.rect.top - 48),
            left: Math.max(8, selection.rect.left + selection.rect.width / 2 - (onCreateAnnotation && onAssignField ? 140 : 90)),
            zIndex: 1050,
            display: "flex",
            gap: 6,
            alignItems: "center",
            padding: "6px 8px",
            background: "var(--color-surface)",
            borderRadius: 8,
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          }}
        >
          {onCreateAnnotation && ANNOTATION_COLORS.map((c) => (
            <Tooltip key={c} title={t("annotation.create")}>
              <button
                type="button"
                onClick={() => handleCreate(c)}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  border: "2px solid var(--color-surface)",
                  boxShadow: "0 0 0 1px var(--color-text-muted)",
                  backgroundColor: c,
                  cursor: "pointer",
                  padding: 0,
                }}
                aria-label={t("annotation.createWithColor", { color: c })}
              />
            </Tooltip>
          ))}
          {onCreateAnnotation && onAssignField && (
            <div style={{ width: 1, height: 20, background: "var(--color-border)", margin: "0 2px" }} />
          )}
          {onAssignField && fieldTypes.length > 0 && (
            <Select
              showSearch
              placeholder={t("annotation.addField")}
              size="small"
              style={{ width: 160, fontSize: 11 }}
              popupMatchSelectWidth={260}
              optionFilterProp="label"
              onChange={(value: string) => {
                onAssignField(selection.selectedText, value);
                window.getSelection()?.removeAllRanges();
                setSelection(null);
              }}
              options={fieldTypes.map((ft) => {
                const hex = ft.category && CATEGORY_COLORS[ft.category]?.hex;
                return {
                  value: ft.fieldId,
                  label: (
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {hex && (
                        <span style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: hex, flexShrink: 0 }} />
                      )}
                      <span style={{ fontWeight: 500 }}>{ft.label}</span>
                      <span style={{ fontSize: 10, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                        {ft.fieldId}
                      </span>
                    </span>
                  ),
                };
              })}
              filterOption={(input, option) => {
                const ft = fieldTypes.find((f) => f.fieldId === option?.value);
                if (!ft) return false;
                const search = `${ft.label} ${ft.fieldId} ${ft.category ?? ""}`.toLowerCase();
                return search.includes(input.toLowerCase());
              }}
            />
          )}
        </div>
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

function AnnotationEditor({
  annotation,
  onUpdate,
  onDelete,
  onDone,
}: {
  annotation: UserAnnotation;
  onUpdate?: (id: string, payload: { color?: string | null; note?: string | null }) => void;
  onDelete?: (id: string) => void;
  onDone: () => void;
}) {
  const { t } = useI18n();
  const [note, setNote] = useState(annotation.note ?? "");
  const [color, setColor] = useState(annotation.color ?? DEFAULT_ANNOTATION_COLOR);

  const handleSave = () => {
    onUpdate?.(annotation.id, { color, note: note.trim() || null });
    onDone();
    message.success(t("annotation.saved"));
  };

  const handleDelete = () => {
    onDelete?.(annotation.id);
    onDone();
    message.success(t("annotation.deleted"));
  };

  return (
    <div style={{ width: 260, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {ANNOTATION_COLORS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setColor(c)}
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              border: color === c ? "2px solid var(--color-text)" : "2px solid var(--color-surface)",
              boxShadow: "0 0 0 1px var(--color-text-muted)",
              backgroundColor: c,
              cursor: "pointer",
              padding: 0,
            }}
            aria-label={t("annotation.pickColor", { color: c })}
          />
        ))}
      </div>
      <Input.TextArea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder={t("annotation.notePlaceholder")}
        autoSize={{ minRows: 2, maxRows: 5 }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <Button
          danger
          size="small"
          icon={<DeleteOutlined />}
          onClick={handleDelete}
          disabled={!onDelete}
        >
          {t("common.delete")}
        </Button>
        <Button type="primary" size="small" onClick={handleSave} disabled={!onUpdate}>
          {t("common.save")}
        </Button>
      </div>
    </div>
  );
}
