import type { UserAnnotation } from "../../types/annotations";
import type { OverlayRect, SelectionInfo, TextNodeOffset } from "./contracts";

export function collectTextNodeOffsets(container: HTMLElement): TextNodeOffset[] {
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

export function offsetToPoint(
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

export function findPointForNode(
  offsets: TextNodeOffset[],
  node: Node,
  offset: number,
): number | null {
  if (node.nodeType === Node.TEXT_NODE) {
    const entry = offsets.find((item) => item.node === node);
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

export function selectionInContainer(container: HTMLElement): SelectionInfo | null {
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

export function computeAnnotationOverlays(
  container: HTMLElement,
  annotations: UserAnnotation[],
): OverlayRect[] {
  const offsets = collectTextNodeOffsets(container);
  const containerRect = container.getBoundingClientRect();
  const overlays: OverlayRect[] = [];

  for (const annotation of annotations) {
    const startPt = offsetToPoint(offsets, annotation.start_offset);
    const endPt = offsetToPoint(offsets, annotation.end_offset);
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
        id: annotation.id,
        top: rect.top - containerRect.top + container.scrollTop,
        left: rect.left - containerRect.left + container.scrollLeft,
        width: rect.width,
        height: rect.height,
      });
    }
  }
  return overlays;
}
