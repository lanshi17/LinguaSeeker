import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PubmedCandidatesPage } from '../pubmed-candidates-page';
import * as api from '../../../services/api';
import { useTaskFlowStore } from '../../../store/useTaskFlowStore';

vi.mock('../../../services/api', () => ({
  pubmedCandidateSearch: vi.fn(),
  pubmedSelectionSubmit: vi.fn(),
  stringifyTaskForm: vi.fn(),
}));

describe('PubmedCandidatesPage M2 Handoff', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTaskFlowStore.setState({
      taskForm: {
        goal: 'test goal',
        disease: 'test disease',
        country: 'test country',
        language: 'test language'
      },
      confirmedRequestId: 'req-123',
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('passes request_id to pubmedCandidateSearch when confirmedRequestId is present', async () => {
    vi.mocked(api.pubmedCandidateSearch).mockResolvedValue({
      task_form: 'test',
      candidates: [
        { pmid: '111', title: 'Paper 1', journal: 'J1', pub_date: '2024' }
      ]
    });

    render(
      <BrowserRouter>
        <PubmedCandidatesPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(api.pubmedCandidateSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          request_id: 'req-123',
          target: 'test goal',
          disease: 'test disease'
        })
      );
    });
  });

  it('passes request_id to pubmedSelectionSubmit when submitted', async () => {
    vi.mocked(api.pubmedCandidateSearch).mockResolvedValue({
      task_form: 'test',
      candidates: [
        { pmid: '111', title: 'Paper 1', journal: 'J1', pub_date: '2024' }
      ]
    });
    vi.mocked(api.pubmedSelectionSubmit).mockResolvedValue({
      request_id: 'req-123',
      status: 'success'
    });

    render(
      <BrowserRouter>
        <PubmedCandidatesPage />
      </BrowserRouter>
    );

    const checkbox = await screen.findByRole('checkbox');
    fireEvent.click(checkbox);

    const submitBtn = screen.getByRole('button', { name: /Submit selection/i });
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.pubmedSelectionSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          request_id: 'req-123',
          selected_pmids: ['111']
        })
      );
    });
  });

  it('shows fallback message when taskForm is missing (sensible fallback)', () => {
    useTaskFlowStore.setState({
      taskForm: null,
      confirmedRequestId: null,
    });

    render(
      <BrowserRouter>
        <PubmedCandidatesPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/Confirmation state or task form not found/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Go to task creation/i })).toBeInTheDocument();
  });
});
