import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LiteratureCandidatesPage } from '../literature-candidates-page';
import * as api from '../../../services/api';
import { useAppStore } from '../../../store/appStore';
import { useTaskFlowStore } from '../../../store/useTaskFlowStore';
import { useToastStore } from '../../../store/useToastStore';

vi.mock('../../../services/api', () => ({
  literatureCandidateSearch: vi.fn(),
  literatureSelectionSubmit: vi.fn(),
  stringifyTaskForm: vi.fn(),
}));

describe('LiteratureCandidatesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAppStore.getState().reset();
    useToastStore.getState().clearToasts();
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
    useAppStore.getState().reset();
    useToastStore.getState().clearToasts();
  });

  it('hydrates AppStore candidates from the search response', async () => {
    vi.mocked(api.literatureCandidateSearch).mockResolvedValue({
      task_form: 'test',
      candidates: [
        { candidate_id: 'cand-1', provider: 'jstage', route: 'api', title: 'Paper 1', language: 'ja' }
      ]
    });

    render(
      <BrowserRouter>
        <LiteratureCandidatesPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(useAppStore.getState().candidates).toEqual([
        expect.objectContaining({ candidate_id: 'cand-1', title: 'Paper 1' })
      ]);
    });
  });

  it('uses selected candidate ids as the shared selection source', async () => {
    useAppStore.setState((state) => ({
      ...state,
      candidates: [
        { candidate_id: 'cand-1', provider: 'jstage', route: 'api', title: 'Paper 1', language: 'ja' }
      ],
      ui: {
        ...state.ui,
        selectedCandidateIds: ['cand-1'],
      },
    }));
    vi.mocked(api.literatureCandidateSearch).mockResolvedValue({
      task_form: 'test',
      candidates: [
        { candidate_id: 'cand-1', provider: 'jstage', route: 'api', title: 'Paper 1', language: 'ja' }
      ]
    });

    render(
      <BrowserRouter>
        <LiteratureCandidatesPage />
      </BrowserRouter>
    );

    expect(await screen.findByRole('checkbox')).toBeChecked();
    expect(screen.getByRole('button', { name: /Submit selection \(1\)/i })).not.toBeDisabled();
  });

  it('passes request_id and selected candidates on submit', async () => {
    vi.mocked(api.literatureCandidateSearch).mockResolvedValue({
      task_form: 'test',
      candidates: [
        { candidate_id: 'cand-1', provider: 'jstage', route: 'api', title: 'Paper 1', language: 'ja' }
      ]
    });
    vi.mocked(api.literatureSelectionSubmit).mockResolvedValue({
      request_id: 'req-123',
      status: 'success'
    });

    render(
      <BrowserRouter>
        <LiteratureCandidatesPage />
      </BrowserRouter>
    );

    const checkbox = await screen.findByRole('checkbox');
    fireEvent.click(checkbox);

    const submitBtn = screen.getByRole('button', { name: /Submit selection/i });
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.literatureSelectionSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          request_id: 'req-123',
          selected_candidates: [expect.objectContaining({ candidate_id: 'cand-1' })]
        })
      );
    });
  });

  it('shows fallback message when taskForm is missing', () => {
    useTaskFlowStore.setState({
      taskForm: null,
      confirmedRequestId: null,
    });

    render(
      <BrowserRouter>
        <LiteratureCandidatesPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/Confirmation state or task form not found/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Go to task creation/i })).toBeInTheDocument();
  });
});
