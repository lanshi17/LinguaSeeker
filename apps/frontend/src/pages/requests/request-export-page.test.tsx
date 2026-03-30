import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/api', () => ({
  getTaskRequestStatus: vi.fn(),
  getEvidenceDocument: vi.fn(),
}));

import { RequestExportPage } from './request-export-page';
import { getEvidenceDocument, getTaskRequestStatus } from '../../services/api';
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
});
