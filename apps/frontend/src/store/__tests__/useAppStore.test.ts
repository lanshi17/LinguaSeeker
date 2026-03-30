import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/api', () => ({
  getTaskRequestStatus: vi.fn(),
  pubmedCandidateSearch: vi.fn(),
}));

import { useAppStore } from '../appStore';
import { useToastStore } from '../useToastStore';
import { getTaskRequestStatus, pubmedCandidateSearch } from '../../services/api';

import type { PubMedCandidateItem, TaskRequestStatusResponse } from '../../types/api';

describe('useAppStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAppStore.getState().reset();
    useToastStore.getState().clearToasts();
  });

  afterEach(() => {
    useAppStore.getState().reset();
    useToastStore.getState().clearToasts();
    vi.useRealTimers();
  });

  it('fetchRequest stores request status for an existing request id', async () => {
    const request: TaskRequestStatusResponse = {
      request_id: 'req-123',
      status: 'running',
      papers: [],
    };
    vi.mocked(getTaskRequestStatus).mockResolvedValueOnce(request);

    await useAppStore.getState().fetchRequest('req-123');

    expect(getTaskRequestStatus).toHaveBeenCalledWith('req-123');
    expect(useAppStore.getState().currentRequest).toEqual(request);
    expect(useAppStore.getState().requestLoading).toBe(false);
    expect(useAppStore.getState().requestError).toBe(null);
  });

  it('fetchCandidates stores candidate results for the current task form payload', async () => {
    const candidates: PubMedCandidateItem[] = [
      { pmid: '1', title: 'A paper', journal: 'Nature', pub_date: '2026-03-01' },
    ];
    vi.mocked(pubmedCandidateSearch).mockResolvedValueOnce({
      request_id: 'req-123',
      task_form: '{"goal":"Assess evidence"}',
      candidates,
    });

    await useAppStore.getState().fetchCandidates({
      request_id: 'req-123',
      target: 'Assess evidence',
      disease: 'Breast cancer',
      source: 'pubmed',
      candidate_limit: 15,
    });

    expect(pubmedCandidateSearch).toHaveBeenCalledWith(
      expect.objectContaining({ request_id: 'req-123', target: 'Assess evidence' })
    );
    expect(useAppStore.getState().candidates).toEqual(candidates);
    expect(useAppStore.getState().candidatesLoading).toBe(false);
    expect(useAppStore.getState().candidatesError).toBe(null);
  });

  it('startRequestPolling stops automatically after the request reaches a terminal status', async () => {
    vi.useFakeTimers();
    vi.mocked(getTaskRequestStatus)
      .mockResolvedValueOnce({ request_id: 'req-123', status: 'running', papers: [] })
      .mockResolvedValueOnce({ request_id: 'req-123', status: 'success', papers: [] });

    useAppStore.getState().startRequestPolling('req-123');
    await vi.advanceTimersByTimeAsync(2100);
    await vi.advanceTimersByTimeAsync(2100);

    expect(getTaskRequestStatus).toHaveBeenCalledTimes(2);
    expect(useAppStore.getState().currentRequest?.status).toBe('success');
    expect(useAppStore.getState().pollingIntervals.has('request-req-123')).toBe(false);
  });

  it('updates task and request filters independently', () => {
    useAppStore.getState().setTaskFilter('status', 'running');
    useAppStore.getState().setRequestFilter('searchQuery', 'req-123');

    expect(useAppStore.getState().ui.taskFilters.status).toBe('running');
    expect(useAppStore.getState().ui.requestFilters.searchQuery).toBe('req-123');
    expect(useAppStore.getState().ui.requestFilters.status).toBe('all');
  });

  it('toggles PMIDs and expanded paper tasks and clears selected PMIDs', () => {
    useAppStore.getState().togglePmidSelection('pmid-1');
    useAppStore.getState().togglePmidSelection('pmid-2');
    useAppStore.getState().togglePaperTaskExpand('paper-1');

    expect(useAppStore.getState().ui.selectedPmids).toEqual(['pmid-1', 'pmid-2']);
    expect(useAppStore.getState().ui.expandedPaperTasks).toEqual(['paper-1']);

    useAppStore.getState().togglePmidSelection('pmid-1');
    useAppStore.getState().clearPmidSelection();
    useAppStore.getState().togglePaperTaskExpand('paper-1');

    expect(useAppStore.getState().ui.selectedPmids).toEqual([]);
    expect(useAppStore.getState().ui.expandedPaperTasks).toEqual([]);
  });

  it('keeps notification compatibility through the existing toast store', () => {
    const id = useToastStore.getState().pushToast({
      level: 'success',
      title: 'Saved',
      message: 'State updated',
      ttlMs: 3000,
    });

    expect(id).toBeTruthy();
    expect(useToastStore.getState().toasts).toContainEqual(
      expect.objectContaining({ title: 'Saved', level: 'success' })
    );
  });
});
