import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/api', () => ({
  getTaskRequestStatus: vi.fn(),
  getEvidenceDocument: vi.fn(),
  getPaperTaskDetail: vi.fn(),
}));

import { RequestExportPage } from './request-export-page';
import { getEvidenceDocument, getPaperTaskDetail, getTaskRequestStatus } from '../../services/api';
import { useAppStore } from '../../store/appStore';
import { useToastStore } from '../../store/useToastStore';

function renderPage(initialPath = '/requests/req-123/export') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/requests/:requestId/export" element={<RequestExportPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('RequestExportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAppStore.getState().reset();
    useToastStore.getState().clearToasts();
  });

  afterEach(() => {
    cleanup();
    useAppStore.getState().reset();
    useToastStore.getState().clearToasts();
  });

  it('hydrates request status into AppStore and auto-selects the first document', async () => {
    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'success',
      papers: [
        {
          paper_task_id: 'paper-1',
          status: 'success',
          document_id: 'doc-1',
        },
      ],
    });
    vi.mocked(getEvidenceDocument).mockResolvedValue({ code: 0, message: 'ok', data: null });

    renderPage();

    await waitFor(() => {
      expect(useAppStore.getState().currentRequest?.request_id).toBe('req-123');
    });
    expect(await screen.findByDisplayValue('doc-1')).toBeInTheDocument();
    expect(getEvidenceDocument).toHaveBeenCalledWith('doc-1', expect.anything());
  });

  it('uses AppStore currentRequest as a shared source when request data is already present', async () => {
    useAppStore.setState({
      currentRequest: {
        request_id: 'req-123',
        status: 'running',
        papers: [
          {
            paper_task_id: 'paper-1',
            status: 'running',
            document_id: 'doc-existing',
          },
        ],
      },
    });
    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'running',
      papers: [
        {
          paper_task_id: 'paper-1',
          status: 'running',
          document_id: 'doc-existing',
        },
      ],
    });
    vi.mocked(getEvidenceDocument).mockResolvedValue({ code: 0, message: 'ok', data: null });

    renderPage();

    expect(await screen.findByDisplayValue('doc-existing')).toBeInTheDocument();
  });

  it('pushes a toast when evidence loading fails', async () => {
    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'success',
      papers: [
        {
          paper_task_id: 'paper-1',
          status: 'success',
          document_id: 'doc-1',
        },
      ],
    });
    vi.mocked(getEvidenceDocument).mockRejectedValue(new Error('boom'));

    renderPage();

    await waitFor(() => {
      expect(useToastStore.getState().toasts).toContainEqual(
        expect.objectContaining({ title: 'Evidence load failed' })
      );
    });
  });

  it('export page renders reading plus judgment sections for print view', async () => {
    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'success',
      papers: [
        {
          paper_task_id: 'paper-1',
          status: 'success',
          document_id: 'doc-1',
        },
      ],
    });
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
      request_id: 'req-123',
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

    expect(await screen.findByText(/Evidence judgment/i)).toBeInTheDocument();
    expect(screen.getByText(/ACMG classification/i)).toBeInTheDocument();
  });
});
