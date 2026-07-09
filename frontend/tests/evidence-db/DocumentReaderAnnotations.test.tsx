import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentReader } from "../../src/features/evidence-db/components/DocumentReader";
import type { EvidenceDocument } from "../../src/features/evidence-search/utils/evidenceDocument";
import type { UserAnnotation } from "../../src/features/evidence-search/types/annotations";

vi.mock("@/features/evidence-search/components/annotationLayer", () => ({
  AnnotationLayer: ({
    paragraphId,
    track,
    annotations,
    onCreateAnnotation,
    onUpdateAnnotation,
    onDeleteAnnotation,
  }: {
    paragraphId: string;
    track: "original" | "translated";
    annotations: UserAnnotation[];
    onCreateAnnotation?: unknown;
    onUpdateAnnotation?: unknown;
    onDeleteAnnotation?: unknown;
  }) => {
    const layerId = `annotation-layer-${track}-${paragraphId}`;
    return (
      <div data-testid={layerId}>
        <span data-testid={`${layerId}-count`}>annotations:{annotations.length}</span>
        <span data-testid={`${layerId}-create`}>
          create:{onCreateAnnotation ? "yes" : "no"}
        </span>
        <span data-testid={`${layerId}-update`}>
          update:{onUpdateAnnotation ? "yes" : "no"}
        </span>
        <span data-testid={`${layerId}-delete`}>
          delete:{onDeleteAnnotation ? "yes" : "no"}
        </span>
      </div>
    );
  },
}));

const SOURCE_DOCUMENT_ID = "123e4567-e89b-12d3-a456-426614174000";

function makeAnnotation(overrides: Partial<UserAnnotation>): UserAnnotation {
  return {
    id: overrides.id ?? "annotation-1",
    source_document_id: SOURCE_DOCUMENT_ID,
    track: "original",
    paragraph_id: "original-full-text",
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

describe("DocumentReader annotations", () => {
  it("feeds full-text and document-level annotations into their visible layers", () => {
    const document: EvidenceDocument = {
      track: "original",
      paragraphs: [
        {
          id: "original-full-text",
          text: "BRCA1 was detected in the proband.",
          highlights: [],
        },
      ],
    };

    render(
      <DocumentReader
        title="Original"
        track="original"
        document={document}
        accentColor="#3B82F6"
        sourceDocumentId={SOURCE_DOCUMENT_ID}
        annotations={[
          makeAnnotation({ id: "full-text", paragraph_id: "original-full-text" }),
          makeAnnotation({ id: "document", paragraph_id: "original-document" }),
        ]}
        onCreateAnnotation={() => undefined}
        onUpdateAnnotation={() => undefined}
        onDeleteAnnotation={() => undefined}
      />,
    );

    const fullTextLayer = "annotation-layer-original-original-full-text";
    const documentLayer = "annotation-layer-original-original-document";

    expect(screen.getByTestId(`${fullTextLayer}-count`)).toHaveTextContent("annotations:1");
    expect(screen.getByTestId(`${fullTextLayer}-create`)).toHaveTextContent("create:yes");
    expect(screen.getByTestId(`${fullTextLayer}-update`)).toHaveTextContent("update:yes");
    expect(screen.getByTestId(`${fullTextLayer}-delete`)).toHaveTextContent("delete:yes");

    expect(screen.getByTestId(`${documentLayer}-count`)).toHaveTextContent("annotations:1");
    expect(screen.getByTestId(`${documentLayer}-create`)).toHaveTextContent("create:yes");
  });
});
