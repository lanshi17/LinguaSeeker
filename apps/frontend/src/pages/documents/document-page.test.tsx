import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/api', () => ({
  getEvidenceDocument: vi.fn(),
  getPaperTaskDetail: vi.fn(),
}));

import { DocumentPage } from './document-page';
import { getEvidenceDocument, getPaperTaskDetail } from '../../services/api';
import { useToastStore } from '../../store/useToastStore';

function renderPage(initialPath = '/documents/doc-1') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/documents/:documentId" element={<DocumentPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('DocumentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useToastStore.getState().clearToasts();
  });

  afterEach(() => {
    cleanup();
    useToastStore.getState().clearToasts();
  });

  it('document page renders stable document evidence payload instead of contract-warning fallback', async () => {
    vi.mocked(getEvidenceDocument).mockResolvedValue({
      code: 0,
      message: 'ok',
      data: {
        source_text: 'source text',
        translated_text: 'translated text',
        ps3_evidence: { strength: 'PS3' },
        graph: { total_evidence: 1 },
      },
    });
    vi.mocked(getPaperTaskDetail).mockResolvedValue({
      paper_task_id: 'paper-1',
      request_id: 'req-1',
      document_id: 'doc-1',
      status: 'success',
      workflow_status: 'COMPLETED',
      processing_steps: {
        classification: { status: 'COMPLETED' },
        adjudication: { status: 'COMPLETED' },
      },
      warning_codes: [],
      trace_chain: {
        steps: {
          classification: { status: 'COMPLETED', outcome: 'success' },
          adjudication: { status: 'COMPLETED', outcome: 'success' },
        },
      },
      fulltext_unavailable: false,
      result_payload: {
        graph_sync_result: { neo4j_ok: true },
      },
      parsing_metadata: { parser_backend: 'mineru' },
      duplicate_of: null,
    });

    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /Evidence judgment/i }));

    expect(await screen.findByText(/Structured evidence/i)).toBeInTheDocument();
    expect(screen.queryByText(/without a stable evidence schema/i)).not.toBeInTheDocument();
  });

  it('document page renders classification and adjudication summary cards', async () => {
    vi.mocked(getEvidenceDocument).mockResolvedValue({
      code: 0,
      message: 'ok',
      data: {
        source_text: 'source text',
        translated_text: 'translated text',
      },
    });
    vi.mocked(getPaperTaskDetail).mockResolvedValue({
      paper_task_id: 'paper-1',
      request_id: 'req-1',
      document_id: 'doc-1',
      status: 'success',
      workflow_status: 'COMPLETED',
      processing_steps: {
        classification: { status: 'COMPLETED' },
        adjudication: { status: 'COMPLETED' },
      },
      warning_codes: [],
      trace_chain: {
        steps: {
          classification: { status: 'COMPLETED', outcome: 'success' },
          adjudication: { status: 'COMPLETED', outcome: 'success' },
        },
      },
      fulltext_unavailable: false,
      result_payload: {
        graph_sync_result: { neo4j_ok: true },
      },
      parsing_metadata: { parser_backend: 'mineru' },
      duplicate_of: null,
    });

    renderPage();

    expect(await screen.findByText(/ACMG classification/i)).toBeInTheDocument();
    expect(screen.getByText(/Expert adjudication/i)).toBeInTheDocument();
  });
});
