import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/api', () => ({
  getTaskRequestStatus: vi.fn(),
  getPaperTaskDetail: vi.fn(),
  reissueLogLink: vi.fn(),
}));

type WorkflowRequest = {
  request_id: string;
  status: string;
  papers: unknown[];
};

type WorkflowTimelineStep = {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  description?: string;
  progress?: number;
};

type WorkflowTask = {
  task_id: string;
  status: string;
  workflow_status?: string;
  workflow_status_description?: string;
  progress_percentage?: number;
  paper_task_id?: string;
  error?: string;
};

type WorkflowState = {
  currentRequest: WorkflowRequest | null;
  currentTask: WorkflowTask | null;
  requestConnection: { requestId: string | null; connected: boolean };
  taskConnection: { taskId: string | null; connected: boolean };
  requestTimeline: WorkflowTimelineStep[];
  taskTimeline: WorkflowTimelineStep[];
  watchRequest: (requestId: string) => void;
  watchTask: (taskId: string) => void;
  reset: () => void;
};

const workflow: { state: WorkflowState } = {
  state: {
    currentRequest: null,
    currentTask: null,
    requestConnection: { requestId: null, connected: false },
    taskConnection: { taskId: null, connected: false },
    requestTimeline: [],
    taskTimeline: [],
    watchRequest: vi.fn(),
    watchTask: vi.fn(),
    reset: vi.fn(),
  },
};

const setWorkflowState = (partial: Partial<WorkflowState>) => {
  workflow.state = {
    ...workflow.state,
    ...partial,
  };
};

vi.mock('../../store/useWorkflowStore', () => ({
  useWorkflowStore: (selector?: (state: WorkflowState) => unknown) =>
    selector ? selector(workflow.state) : (workflow.state as unknown),
}));

import { getPaperTaskDetail, getTaskRequestStatus, reissueLogLink } from '../../services/api';
import { useAppStore } from '../../store/appStore';
import { useToastStore } from '../../store/useToastStore';

async function renderPage(initialPath = '/requests/req-123') {
  const { RequestMonitorPage } = await import('./request-monitor-page');

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/requests/:requestId" element={<RequestMonitorPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('RequestMonitorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAppStore.getState().reset();
    useToastStore.getState().clearToasts();

    setWorkflowState({
      currentRequest: null,
      currentTask: null,
      requestConnection: { requestId: null, connected: false },
      taskConnection: { taskId: null, connected: false },
      requestTimeline: [],
      taskTimeline: [],
      watchRequest: vi.fn(),
      watchTask: vi.fn(),
      reset: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
    useAppStore.getState().reset();
    useToastStore.getState().clearToasts();
  });

  it('prefers matching active workflow stream over polling snapshot', async () => {
    const watchRequest = vi.fn();

    setWorkflowState({
      currentRequest: {
        request_id: 'req-123',
        status: 'success',
        papers: [],
      },
      requestTimeline: [
        { id: 'queued', label: 'Queued', status: 'completed' },
        { id: 'running', label: 'Running', status: 'completed' },
        { id: 'success', label: 'Completed', status: 'completed' },
      ],
      requestConnection: { requestId: 'req-123', connected: true },
      watchRequest,
      reset: vi.fn(),
    });

    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'running',
      papers: [],
    });

    await renderPage();

    expect(await screen.findByText('success')).toBeInTheDocument();
    expect(screen.queryByText('running')).not.toBeInTheDocument();
    expect(watchRequest).toHaveBeenCalledWith('req-123');
    await waitFor(() => {
      expect(getTaskRequestStatus).toHaveBeenCalledTimes(1);
    });
  });

  it('falls back to polling snapshot when no matching stream data is active', async () => {
    setWorkflowState({
      currentRequest: {
        request_id: 'req-other',
        status: 'success',
        papers: [],
      },
      requestConnection: { requestId: 'req-other', connected: true },
      requestTimeline: [],
    });

    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'running',
      papers: [
        {
          paper_task_id: 'paper-1',
          status: 'queued',
          filename: 'paper.pdf',
          document_id: 'doc-1',
        },
      ],
    });

    await renderPage();

    expect(await screen.findByText('running')).toBeInTheDocument();
    expect(screen.getByText('paper.pdf')).toBeInTheDocument();
  });

  it('falls back to app-store request when stream and poll data are absent', async () => {
    useAppStore.setState({
      currentRequest: {
        request_id: 'req-123',
        status: 'queued',
        papers: [],
      },
    });

    vi.mocked(getTaskRequestStatus).mockRejectedValue(new Error('network down'));

    await renderPage();

    expect(await screen.findByText('queued')).toBeInTheDocument();
    expect(screen.queryByText('Error')).not.toBeInTheDocument();
    expect(screen.queryByText('network down')).not.toBeInTheDocument();
    expect(useAppStore.getState().currentRequest?.request_id).toBe('req-123');
  });

  it('renders shared timeline states for request and paper-task workflows', async () => {
    const watchTask = vi.fn();

    setWorkflowState({
      currentRequest: {
        request_id: 'req-123',
        status: 'running',
        papers: [
          {
            paper_task_id: 'paper-1',
            status: 'failure',
            filename: 'paper.pdf',
          },
        ],
      },
      requestConnection: { requestId: 'req-123', connected: true },
      requestTimeline: [
        { id: 'queued', label: 'Queued', status: 'completed' },
        { id: 'running', label: 'Running', status: 'running', description: 'Parsing PDF', progress: 40 },
        { id: 'success', label: 'Completed', status: 'error', description: 'Workflow failed' },
      ],
      currentTask: {
        task_id: 'task-1',
        status: 'failure',
        workflow_status: 'classification',
        workflow_status_description: 'Classifier crashed',
        progress_percentage: 60,
        paper_task_id: 'paper-1',
        error: 'Classifier crashed',
      },
      taskConnection: { taskId: 'task-1', connected: true },
      taskTimeline: [
        { id: 'queued', label: 'Queued', status: 'completed' },
        { id: 'running', label: 'Running', status: 'completed', description: 'Parsed PDF', progress: 60 },
        { id: 'failed', label: 'Failed', status: 'error', description: 'Classifier crashed' },
      ],
      watchTask,
    });

    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'queued',
      papers: [
        {
          paper_task_id: 'paper-1',
          status: 'failure',
          filename: 'paper.pdf',
        },
      ],
    });

    await renderPage();

    expect(await screen.findByText('Workflow')).toBeInTheDocument();
    expect(screen.getByText(/Parsing PDF/i)).toBeInTheDocument();
    expect(screen.getByText(/Workflow failed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Details/i }));

    expect(screen.getByText(/Task workflow/i)).toBeInTheDocument();
    expect(screen.getByText(/^Failed$/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Classifier crashed/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/error/i).length).toBeGreaterThan(0);
  });

  it('toggles paper details expansion through AppStore state', async () => {
    const watchTask = vi.fn();

    setWorkflowState({
      currentTask: {
        task_id: 'task-1',
        status: 'started',
        workflow_status: 'parsing',
        workflow_status_description: 'Parsing PDF',
        progress_percentage: 60,
        paper_task_id: 'paper-1',
      },
      taskConnection: { taskId: 'task-1', connected: true },
      taskTimeline: [
        { id: 'queued', label: 'Queued', status: 'completed' },
        { id: 'running', label: 'Running', status: 'running', description: 'Parsing PDF', progress: 60 },
        { id: 'success', label: 'Completed', status: 'pending' },
      ],
      watchTask,
    });

    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'success',
      papers: [
        {
          paper_task_id: 'paper-1',
          status: 'success',
          filename: 'paper.pdf',
          error_code: 'FILE_DUPLICATE',
          duplicate_of: 'paper-0',
        },
      ],
    });

    await renderPage();

    expect(await screen.findByText('paper.pdf')).toBeInTheDocument();
    expect(screen.queryByText(/paper_task_id:/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Details/i }));

    expect(useAppStore.getState().ui.expandedPaperTasks).toContain('paper-1');
    expect(screen.getByText(/paper_task_id: paper-1/i)).toBeInTheDocument();
    expect(screen.getByText(/error_code: FILE_DUPLICATE/i)).toBeInTheDocument();
    expect(screen.getByText(/duplicate_of: paper-0/i)).toBeInTheDocument();
    expect(screen.getByText(/Task workflow/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Parsing PDF/i)).toHaveLength(2);
    expect(screen.getByText(/60%/i)).toBeInTheDocument();
    expect(watchTask).toHaveBeenCalledWith('paper-1');

    fireEvent.click(screen.getByRole('button', { name: /Hide details/i }));

    expect(useAppStore.getState().ui.expandedPaperTasks).toEqual([]);
    expect(screen.queryByText(/paper_task_id: paper-1/i)).not.toBeInTheDocument();
  });

  it('pushes a toast when reissuing the log link fails', async () => {
    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'running',
      papers: [],
    });
    vi.mocked(reissueLogLink).mockRejectedValue(new Error('boom'));

    await renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /Reissue log link/i }));

    await waitFor(() => {
      expect(useToastStore.getState().toasts).toContainEqual(
        expect.objectContaining({ title: 'Log link reissue failed' })
      );
    });
  });

  it('renders duplicate/fulltext labels and 6-node detail from paper task detail API', async () => {
    setWorkflowState({
      currentRequest: null,
      requestTimeline: [],
      requestConnection: { requestId: null, connected: false },
    });

    vi.mocked(getTaskRequestStatus).mockResolvedValue({
      request_id: 'req-123',
      status: 'success',
      papers: [
        {
          paper_task_id: 'paper-1',
          status: 'success',
          filename: 'paper.pdf',
          error_code: 'FILE_DUPLICATE',
          duplicate_of: 'paper-0',
          document_id: 'doc-1',
        },
      ],
    });
    vi.mocked(getPaperTaskDetail).mockResolvedValue({
      paper_task_id: 'paper-1',
      request_id: 'req-123',
      document_id: 'doc-1',
      status: 'success',
      workflow_status: 'COMPLETED',
      processing_steps: {
        acquisition: { status: 'COMPLETED' },
        parsing: { status: 'SKIPPED' },
        translation: { status: 'COMPLETED' },
        extraction: { status: 'COMPLETED' },
        classification: { status: 'COMPLETED' },
        adjudication: { status: 'COMPLETED' },
      },
      warning_codes: ['FULLTEXT_UNAVAILABLE'],
      trace_chain: {
        steps: {
          acquisition: { status: 'COMPLETED', outcome: 'success' },
          classification: { status: 'COMPLETED', outcome: 'success' },
          adjudication: { status: 'COMPLETED', outcome: 'success' },
        },
      },
      fulltext_unavailable: true,
      result_payload: {
        graph_sync_result: { neo4j_ok: true },
      },
      parsing_metadata: { parser_backend: 'mineru' },
      duplicate_of: 'paper-0',
    });

    await renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /Details/i }));

    expect(await screen.findByText(/fulltext unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/classification/i)).toBeInTheDocument();
    expect(screen.getByText(/adjudication/i)).toBeInTheDocument();
  });
});
