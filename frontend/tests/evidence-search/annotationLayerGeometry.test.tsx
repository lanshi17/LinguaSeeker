import { afterEach, describe, expect, it, vi } from "vitest";

import type { UserAnnotation } from "../../src/features/evidence-search/types/annotations";
import {
  collectTextNodeOffsets,
  computeAnnotationOverlays,
  selectionInContainer,
} from "../../src/features/evidence-search/components/annotation-layer/geometry";

function makeRect(
  x: number,
  y: number,
  width: number,
  height: number,
): DOMRect {
  return new DOMRect(x, y, width, height);
}

function makeAnnotation(overrides: Partial<UserAnnotation>): UserAnnotation {
  return {
    id: "annotation-1",
    source_document_id: "document-1",
    track: "original",
    paragraph_id: "paragraph-1",
    start_offset: 0,
    end_offset: 5,
    color: "#fde68a",
    note: null,
    author: "tester",
    created_at: "2026-07-08T00:00:00Z",
    updated_at: "2026-07-08T00:00:00Z",
    ...overrides,
  };
}

function textNode(node: ChildNode | null | undefined): Text {
  if (!(node instanceof Text)) {
    throw new Error("Expected a text node");
  }
  return node;
}

function setRangeClientRects(rects: DOMRect[]): void {
  Object.defineProperty(Range.prototype, "getClientRects", {
    configurable: true,
    value: () => rects,
  });
}

function setRangeBoundingRect(rect: DOMRect): void {
  Object.defineProperty(Range.prototype, "getBoundingClientRect", {
    configurable: true,
    value: () => rect,
  });
}

afterEach(() => {
  document.body.replaceChildren();
  window.getSelection()?.removeAllRanges();
  vi.restoreAllMocks();
});

describe("annotation layer geometry", () => {
  it("collects visible descendant text offsets in flattened order", () => {
    const container = document.createElement("div");
    container.append(document.createTextNode("BRCA"));
    const strong = document.createElement("strong");
    strong.textContent = "1";
    container.append(strong);
    container.append(document.createTextNode(" evidence"));

    const offsets = collectTextNodeOffsets(container).map((offset) => ({
      text: offset.node.textContent,
      start: offset.start,
    }));

    expect(offsets).toEqual([
      { text: "BRCA", start: 0 },
      { text: "1", start: 4 },
      { text: " evidence", start: 5 },
    ]);
  });

  it("maps a DOM selection back to flattened annotation offsets", () => {
    const container = document.createElement("div");
    container.innerHTML = "<span>BRCA</span>1 <strong>evidence</strong>";
    document.body.append(container);
    const selectionRect = makeRect(12, 24, 80, 16);
    setRangeBoundingRect(selectionRect);

    const range = document.createRange();
    range.setStart(textNode(container.querySelector("span")?.firstChild), 2);
    range.setEnd(textNode(container.querySelector("strong")?.firstChild), 4);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);

    expect(selectionInContainer(container)).toMatchObject({
      start_offset: 2,
      end_offset: 10,
      rect: selectionRect,
      selectedText: "CA1 evid",
    });
  });

  it("computes annotation overlay rectangles relative to the paragraph container", () => {
    const container = document.createElement("div");
    container.textContent = "BRCA1 evidence";
    document.body.append(container);
    vi.spyOn(container, "getBoundingClientRect").mockReturnValue(makeRect(10, 20, 300, 120));
    Object.defineProperty(container, "scrollTop", { configurable: true, value: 3 });
    Object.defineProperty(container, "scrollLeft", { configurable: true, value: 2 });
    setRangeClientRects([
      makeRect(15, 25, 30, 12),
      makeRect(18, 30, 0.5, 12),
      makeRect(40, 45, 50, 14),
    ]);

    const overlays = computeAnnotationOverlays(container, [
      makeAnnotation({ id: "annotation-1", start_offset: 0, end_offset: 5 }),
    ]);

    expect(overlays).toEqual([
      { id: "annotation-1", top: 8, left: 7, width: 30, height: 12 },
      { id: "annotation-1", top: 28, left: 32, width: 50, height: 14 },
    ]);
  });
});
