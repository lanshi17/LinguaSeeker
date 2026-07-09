import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntdApp } from "antd";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BilingualCompareView } from "../../src/features/evidence-search/components/BilingualCompareView";
import {
  createAnnotation,
  deleteAnnotation,
  listAnnotations,
  updateAnnotation,
} from "@/features/evidence-search/services/annotations";
import { patchEvidence } from "@/features/evidence-search/services/evidenceCorrection";
import type { UserAnnotation } from "../../src/features/evidence-search/types/annotations";
import type { EvidenceGroupDetailResponse } from "../../src/features/evidence-search/types/evidenceSearch";

vi.mock("@/features/evidence-search/services/annotations", () => ({
  listAnnotations: vi.fn(),
  createAnnotation: vi.fn(),
  updateAnnotation: vi.fn(),
  deleteAnnotation: vi.fn(),
}));

vi.mock("@/features/evidence-search/services/evidenceCorrection", () => ({
  patchEvidence: vi.fn(),
}));

vi.mock("../../src/features/evidence-search/components/annotationLayer", () => {
  type MockAnnotation = {
    id: string;
    note: string | null;
  };
  type MockFieldType = {
    fieldId: string;
  };
  type MockLayerProps = {
    paragraphId: string;
    track: "original" | "translated";
    annotations: MockAnnotation[];
    fieldTypes?: MockFieldType[];
    onCreateAnnotation?: (payload: {
      paragraph_id: string;
      track: "original" | "translated";
      start_offset: number;
      end_offset: number;
      color: string;
    }) => void | Promise<void>;
    onUpdateAnnotation?: (
      id: string,
      payload: { color?: string | null; note?: string | null },
    ) => void | Promise<void>;
    onDeleteAnnotation?: (id: string) => void | Promise<void>;
    onAssignField?: (selectedText: string, fieldType: string) => void | Promise<void>;
  };

  return {
    AnnotationLayer: ({
      paragraphId,
      track,
      annotations,
      fieldTypes = [],
      onCreateAnnotation,
      onUpdateAnnotation,
      onDeleteAnnotation,
      onAssignField,
    }: MockLayerProps) => {
      const layerId = `annotation-layer-${track}-${paragraphId}`;
      const firstAnnotation = annotations[0];
      const fieldIds = fieldTypes.map((fieldType) => fieldType.fieldId);
      return (
        <div data-testid={layerId}>
          <span data-testid={`${layerId}-count`}>annotations:{annotations.length}</span>
          <span data-testid={`${layerId}-note`}>
            {firstAnnotation?.note ?? "none"}
          </span>
          <span data-testid={`${layerId}-fields`}>
            {fieldIds.join(",")}
          </span>
          <button
            type="button"
            data-testid={`${layerId}-create`}
            onClick={() => {
              void onCreateAnnotation?.({
                paragraph_id: paragraphId,
                track,
                start_offset: 0,
                end_offset: 5,
                color: "#fde68a",
              });
            }}
          >
            create
          </button>
          <button
            type="button"
            data-testid={`${layerId}-update`}
            disabled={!firstAnnotation}
            onClick={() => {
              if (!firstAnnotation) return;
              void onUpdateAnnotation?.(firstAnnotation.id, {
                color: "#bbf7d0",
                note: null,
              });
            }}
          >
            update
          </button>
          <button
            type="button"
            data-testid={`${layerId}-delete`}
            disabled={!firstAnnotation}
            onClick={() => {
              if (!firstAnnotation) return;
              void onDeleteAnnotation?.(firstAnnotation.id);
            }}
          >
            delete
          </button>
          <button
            type="button"
            data-testid={`${layerId}-assign-gene`}
            disabled={!onAssignField || !fieldIds.includes("A.gene_symbol")}
            onClick={() => {
              void onAssignField?.("BRCA1", "A.gene_symbol");
            }}
          >
            assign gene
          </button>
        </div>
      );
    },
  };
});

const SOURCE_DOCUMENT_ID = "123e4567-e89b-12d3-a456-426614174000";

function makeDetail(overrides: Partial<EvidenceGroupDetailResponse> = {}): EvidenceGroupDetailResponse {
  return {
    group_id: "group-1",
    source_document_id: SOURCE_DOCUMENT_ID,
    title: "BRCA1 evidence paper",
    pmid: null,
    doi: null,
    original_document_text: "BRCA1 was detected in the proband.",
    translated_document_text: null,
    gene: "BRCA1",
    variant: null,
    disease: null,
    classification: null,
    item_count: 1,
    avg_confidence: 0.9,
    distribution: {
      by_category: {},
      by_field: {},
      by_status: {},
      by_track: {},
    },
    items: [{
      canonical_evidence_id: "evidence-1",
      field_id: "A.gene_symbol",
      field_name: "Gene symbol",
      category: "A",
      value: "BRCA1",
      review_status: "provisional",
      confidence: 0.9,
      track: "original",
      page: 1,
    }],
    traces: [{
      canonical_evidence_id: "evidence-1",
      field_id: "A.gene_symbol",
      field_name: "Gene symbol",
      original_value: "BRCA1",
      translated_value: null,
      alignment_confidence: 0.9,
      original: {
        text: "BRCA1 was detected in the proband.",
        highlight_start: 0,
        highlight_end: 5,
        page: 1,
        source_span: {},
      },
      translated: null,
    }],
    ...overrides,
  };
}

function makeAnnotation(overrides: Partial<UserAnnotation> = {}): UserAnnotation {
  return {
    id: "annotation-1",
    source_document_id: SOURCE_DOCUMENT_ID,
    track: "original",
    paragraph_id: "original-full-text",
    start_offset: 0,
    end_offset: 5,
    color: "#fde68a",
    note: "saved note",
    author: "tester",
    created_at: "2026-07-08T00:00:00Z",
    updated_at: "2026-07-08T00:00:00Z",
    ...overrides,
  };
}

function renderCompare(detail: EvidenceGroupDetailResponse) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });

  const view = render(
    <MemoryRouter>
      <AntdApp>
        <QueryClientProvider client={queryClient}>
          <BilingualCompareView
            detail={detail}
            groupId={detail.group_id}
            selectedEvidenceId="evidence-1"
            setSelectedEvidenceId={() => undefined}
          />
        </QueryClientProvider>
      </AntdApp>
    </MemoryRouter>,
  );

  return { queryClient, ...view };
}

describe("BilingualCompareView annotations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("writes a created annotation into the visible reader cache immediately after the server confirms it", async () => {
    const created = makeAnnotation();
    let serverAnnotations: UserAnnotation[] = [];
    vi.mocked(listAnnotations).mockImplementation(async () => serverAnnotations);
    vi.mocked(createAnnotation).mockImplementation(async () => {
      serverAnnotations = [created];
      return created;
    });

    renderCompare(makeDetail());
    const countId = "annotation-layer-original-original-full-text-count";
    const createId = "annotation-layer-original-original-full-text-create";

    await screen.findByTestId(createId);
    expect(screen.getByTestId(countId)).toHaveTextContent("annotations:0");

    fireEvent.click(screen.getByTestId(createId));

    await waitFor(() => {
      expect(createAnnotation).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId(countId)).toHaveTextContent("annotations:1");
    });
  });

  it("mirrors a created annotation into the translated reader", async () => {
    const created = makeAnnotation({
      paragraph_id: "original-full-text",
      track: "original",
      start_offset: 0,
      end_offset: 5,
    });
    let serverAnnotations: UserAnnotation[] = [];
    vi.mocked(listAnnotations).mockImplementation(async () => serverAnnotations);
    vi.mocked(createAnnotation).mockImplementation(async () => {
      serverAnnotations = [created];
      return created;
    });

    renderCompare(makeDetail({
      translated_document_text: "BRCA1 was detected in the proband.",
      translation_alignment: [{
        chunk_id: "chunk-1",
        original_text: "BRCA1 was detected in the proband.",
        english_text: "BRCA1 was detected in the proband.",
        original_start_offset: 0,
        original_end_offset: 33,
        english_start_offset: 0,
        english_end_offset: 33,
        page: 1,
        block_index: 0,
        span_pairs: [{
          pair_id: "pair-1",
          original_text: "BRCA1",
          english_text: "BRCA1",
          original_start_offset: 0,
          original_end_offset: 5,
          english_start_offset: 0,
          english_end_offset: 5,
          confidence: 0.99,
          method: "deterministic_token",
        }],
      }],
    }));

    const originalCreateId = "annotation-layer-original-original-full-text-create";
    const translatedCountId = "annotation-layer-translated-translated-full-text-count";

    await screen.findByTestId(originalCreateId);
    expect(screen.getByTestId(translatedCountId)).toHaveTextContent("annotations:0");

    fireEvent.click(screen.getByTestId(originalCreateId));

    await waitFor(() => {
      expect(screen.getByTestId(translatedCountId)).toHaveTextContent("annotations:1");
    });
  });

  it("keeps update and delete mutations synchronized with the visible reader cache", async () => {
    const initial = makeAnnotation();
    const updated = makeAnnotation({
      color: "#bbf7d0",
      note: null,
      updated_at: "2026-07-08T00:01:00Z",
    });
    let serverAnnotations: UserAnnotation[] = [initial];
    vi.mocked(listAnnotations).mockImplementation(async () => serverAnnotations);
    vi.mocked(updateAnnotation).mockImplementation(async () => {
      serverAnnotations = [updated];
      return updated;
    });
    vi.mocked(deleteAnnotation).mockImplementation(async () => {
      serverAnnotations = [];
    });

    renderCompare(makeDetail());
    const layerPrefix = "annotation-layer-original-original-full-text";

    await waitFor(() => {
      expect(screen.getByTestId(`${layerPrefix}-count`)).toHaveTextContent("annotations:1");
      expect(screen.getByTestId(`${layerPrefix}-note`)).toHaveTextContent("saved note");
    });

    fireEvent.click(screen.getByTestId(`${layerPrefix}-update`));

    await waitFor(() => {
      expect(updateAnnotation).toHaveBeenCalledWith(
        SOURCE_DOCUMENT_ID,
        "annotation-1",
        { color: "#bbf7d0", note: null },
      );
      expect(screen.getByTestId(`${layerPrefix}-note`)).toHaveTextContent("none");
    });

    fireEvent.click(screen.getByTestId(`${layerPrefix}-delete`));

    await waitFor(() => {
      expect(deleteAnnotation).toHaveBeenCalledWith(SOURCE_DOCUMENT_ID, "annotation-1");
      expect(screen.getByTestId(`${layerPrefix}-count`)).toHaveTextContent("annotations:0");
    });
  });

  it("renders trace fallback paragraphs once when no full document text is available", async () => {
    vi.mocked(listAnnotations).mockResolvedValue([]);
    renderCompare(makeDetail({ original_document_text: null }));

    const fallbackLayerId = "annotation-layer-original-original-evidence-1-0";
    await screen.findByTestId(fallbackLayerId);

    expect(screen.getAllByTestId(fallbackLayerId)).toHaveLength(1);
  });

  it("maps assigned catalog fields to backend patch fields", async () => {
    vi.mocked(listAnnotations).mockResolvedValue([]);
    vi.mocked(patchEvidence).mockResolvedValue({
      canonical_evidence_id: "evidence-1",
      old_status: "provisional",
      new_status: "corrected",
      deltas: 1,
      field_deltas: [],
    });

    renderCompare(makeDetail({
      items: [
        {
          canonical_evidence_id: "evidence-1",
          field_id: "A.gene_symbol",
          field_name: "Gene symbol",
          category: "A",
          value: "BRCA1",
          review_status: "provisional",
          confidence: 0.9,
          track: "original",
          page: 1,
        },
        {
          canonical_evidence_id: "evidence-2",
          field_id: "B.sex",
          field_name: "Sex",
          category: "B",
          value: "female",
          review_status: "provisional",
          confidence: 0.8,
          track: "original",
          page: 1,
        },
      ],
    }));

    const layerPrefix = "annotation-layer-original-original-full-text";
    await screen.findByTestId(`${layerPrefix}-assign-gene`);

    expect(screen.getByTestId(`${layerPrefix}-fields`)).toHaveTextContent("A.gene_symbol");
    expect(screen.getByTestId(`${layerPrefix}-fields`)).not.toHaveTextContent("B.sex");

    fireEvent.click(screen.getByTestId(`${layerPrefix}-assign-gene`));

    await waitFor(() => {
      expect(patchEvidence).toHaveBeenCalledWith("evidence-1", {
        fields: { gene: "BRCA1" },
        change_reason: "Text selection assignment to A.gene_symbol",
      });
    });
  });

  it("updates the current group-detail cache after field assignment without waiting for a refetch", async () => {
    vi.mocked(listAnnotations).mockResolvedValue([]);
    vi.mocked(patchEvidence).mockResolvedValue({
      canonical_evidence_id: "evidence-1",
      old_status: "provisional",
      new_status: "corrected",
      deltas: 1,
      field_deltas: [],
    });

    const staleDetail = makeDetail({
      gene: "OLD",
      items: [
        {
          canonical_evidence_id: "evidence-1",
          field_id: "A.gene_symbol",
          field_name: "Gene symbol",
          category: "A",
          value: "OLD",
          review_status: "provisional",
          confidence: 0.9,
          track: "original",
          page: 1,
        },
      ],
      distribution: {
        by_category: {},
        by_field: {},
        by_status: { provisional: 1 },
        by_track: {},
      },
    });

    const { queryClient } = renderCompare(staleDetail);
    const queryKey = ["evidence", "group-detail", staleDetail.group_id, undefined] as const;
    queryClient.setQueryData<EvidenceGroupDetailResponse>(queryKey, staleDetail);

    const layerPrefix = "annotation-layer-original-original-full-text";
    await screen.findByTestId(`${layerPrefix}-assign-gene`);
    expect(screen.getAllByText("OLD").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByTestId(`${layerPrefix}-assign-gene`));

    await waitFor(() => {
      expect(queryClient.getQueryData<EvidenceGroupDetailResponse>(queryKey)).toMatchObject({
        gene: "BRCA1",
        items: [{ value: "BRCA1", review_status: "corrected" }],
        distribution: { by_status: { corrected: 1 } },
      });
    });
    await waitFor(() => {
      expect(screen.queryByText("OLD")).not.toBeInTheDocument();
    });
    expect(screen.getAllByText("corrected").length).toBeGreaterThan(0);
  });

  it("updates the current group-detail cache after inline review without waiting for a refetch", async () => {
    vi.mocked(listAnnotations).mockResolvedValue([]);
    vi.mocked(patchEvidence).mockResolvedValue({
      canonical_evidence_id: "evidence-1",
      old_status: "provisional",
      new_status: "approved",
      deltas: 1,
      field_deltas: [],
    });

    const staleDetail = makeDetail({
      distribution: {
        by_category: {},
        by_field: {},
        by_status: { provisional: 1 },
        by_track: {},
      },
    });

    const { queryClient } = renderCompare(staleDetail);
    const queryKey = ["evidence", "group-detail", staleDetail.group_id, undefined] as const;
    queryClient.setQueryData<EvidenceGroupDetailResponse>(queryKey, staleDetail);

    const evidenceMark = await screen.findByLabelText(/Gene symbol/);
    fireEvent.click(evidenceMark, { clientX: 16, clientY: 16 });

    fireEvent.click(await screen.findByRole("button", { name: /批准|Approve/ }));

    await waitFor(() => {
      expect(patchEvidence).toHaveBeenCalledWith("evidence-1", {
        fields: {},
        new_status: "approved",
      });
      expect(queryClient.getQueryData<EvidenceGroupDetailResponse>(queryKey)).toMatchObject({
        items: [{ review_status: "approved" }],
        distribution: { by_status: { approved: 1 } },
      });
    });
    expect(screen.getAllByText("approved").length).toBeGreaterThan(0);
  });
});
