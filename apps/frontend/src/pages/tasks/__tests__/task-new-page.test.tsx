import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TaskNewPage } from '../task-new-page';
import { useTaskFlowStore } from '../../../store/useTaskFlowStore';
import { useToastStore } from '../../../store/useToastStore';
import { confirmTaskForm, uploadTaskRequest } from '../../../services/api';

vi.mock('../../../components/chat/agent-clarification-chat', () => ({
  AgentClarificationChat: () => <div>Mock clarification chat</div>,
}));

vi.mock('../../../services/api', () => ({
  confirmTaskForm: vi.fn(),
  uploadTaskRequest: vi.fn(),
  interactionStart: vi.fn(),
  interactionRespond: vi.fn(),
}));

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <TaskNewPage />
    </MemoryRouter>
  );
}

describe('TaskNewPage shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTaskFlowStore.setState({
      taskForm: {
        goal: 'Assess PS3 evidence',
        disease: 'Breast cancer',
        country: 'CN',
        language: 'en',
      },
      interactionSessionId: null,
      interactionRound: 1,
      entryMode: 'documents',
      taskFormPayload: { goal: 'Assess PS3 evidence' },
      confirmedRequestId: null,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders clarification, task-sheet confirmation, and branch actions zones', () => {
    renderPage();

    expect(screen.getByRole('heading', { name: /Clarification/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Task-sheet confirmation/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Branch actions/i })).toBeInTheDocument();
  });

  it('shows the clarification round counter', () => {
    renderPage();
    expect(screen.getByText('Clarification rounds: 1/2')).toBeInTheDocument();
  });

  it('shows an expert feedback panel with next-step guidance', () => {
    renderPage();

    expect(screen.getByRole('heading', { name: /Expert feedback/i })).toBeInTheDocument();
    expect(screen.getByText(/Confirm the task form to lock the request id before branching\./i)).toBeInTheDocument();
  });

  it('provides a confirm-now action in expert feedback', async () => {
    vi.mocked(confirmTaskForm).mockResolvedValueOnce({
      confirmed: true,
      request_id: 'req-from-feedback',
      available_branches: [{ source: 'upload' }, { source: 'pubmed' }],
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: /Confirm now/i }));

    await waitFor(() => {
      expect(confirmTaskForm).toHaveBeenCalledWith(
        expect.objectContaining({
          task_form_payload: expect.objectContaining({ goal: 'Assess PS3 evidence' }),
        })
      );
    });

    expect(screen.getByText(/Confirmed!/i)).toBeInTheDocument();
    expect(screen.getByText(/req-from-feedback/i)).toBeInTheDocument();
  });

  it('shows default country and language values when the task form is auto-generated later', () => {
    useTaskFlowStore.setState({
      taskForm: null,
      interactionRound: 0,
      taskFormPayload: null,
      confirmedRequestId: null,
    });

    renderPage();

    expect(screen.getByDisplayValue('不限')).toBeInTheDocument();
    expect(screen.getByDisplayValue('auto')).toBeInTheDocument();
  });

  it('keeps structured fields visible and editable', () => {
    renderPage();

    const goalInput = screen.getByDisplayValue('Assess PS3 evidence');
    fireEvent.change(goalInput, { target: { value: 'Assess BS3 evidence' } });

    expect(screen.getByDisplayValue('Assess BS3 evidence')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Breast cancer')).toBeInTheDocument();
    expect(screen.getByDisplayValue('CN')).toBeInTheDocument();
    expect(screen.getByDisplayValue('en')).toBeInTheDocument();
  });

  it('enables branch actions after confirmation', () => {
    useTaskFlowStore.setState({
      confirmedRequestId: 'req-123',
    });

    renderPage();

    expect(screen.getByText(/Confirmed!/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go to candidates/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit upload/i })).toBeDisabled();
  });
});

describe('TaskNewPage branches (upload and skip-upload)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTaskFlowStore.setState({
      taskForm: {
        goal: 'Assess PS3 evidence',
        disease: 'Breast cancer',
        country: 'CN',
        language: 'en',
      },
      interactionSessionId: null,
      interactionRound: 1,
      entryMode: 'documents',
      taskFormPayload: { goal: 'Assess PS3 evidence' },
      confirmedRequestId: 'req-123',
    });
    useToastStore.setState({ toasts: [] });
  });

  afterEach(() => {
    cleanup();
  });

  it('Upload: valid confirmed request + valid files calls uploadTaskRequest and navigates to /requests/:request_id', async () => {
    vi.mocked(uploadTaskRequest).mockResolvedValueOnce({
      request_id: 'req-123',
      status: 'queued',
    });
    renderPage();

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['hello'], 'test.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    const submitBtn = screen.getByRole('button', { name: /Submit upload/i });
    expect(submitBtn).not.toBeDisabled();

    fireEvent.click(submitBtn);

    expect(uploadTaskRequest).toHaveBeenCalledWith('req-123', [file]);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/requests/req-123');
    });
  });

  it('Upload: invalid file locally blocks submission, shows toast, and uploadTaskRequest is NOT called', () => {
    renderPage();

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const largeContent = new Array(11 * 1024 * 1024).fill('a').join('');
    const file = new File([largeContent], 'large.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    const submitBtn = screen.getByRole('button', { name: /Submit upload/i });
    fireEvent.click(submitBtn);

    expect(uploadTaskRequest).not.toHaveBeenCalled();

    const toasts = useToastStore.getState().toasts;
    expect(toasts).toContainEqual(
      expect.objectContaining({
        level: 'error',
        title: 'Upload validation failed',
      })
    );
  });

  it('Skip-upload: clicking candidates performs handoff and routes to candidates page, disabled while busy', () => {
    renderPage();

    const skipBtn = screen.getByRole('button', { name: /Go to candidates/i });
    expect(skipBtn).not.toBeDisabled();

    fireEvent.click(skipBtn);

    expect(mockNavigate).toHaveBeenCalledWith('/tasks/pubmed/candidates');
    expect(useTaskFlowStore.getState().confirmedRequestId).toBe('req-123');
  });

  it('Branch actions lock during submission so users cannot double-submit', async () => {
    let resolveUpload: ((value: { request_id: string; status: string }) => void) | undefined;
    vi.mocked(uploadTaskRequest).mockImplementationOnce(() => {
      return new Promise((resolve) => {
        resolveUpload = resolve;
      });
    });

    renderPage();

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['hello'], 'test.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    const submitBtn = screen.getByRole('button', { name: /Submit upload/i });
    fireEvent.click(submitBtn);

    expect(submitBtn).toBeDisabled();

    const skipBtn = screen.getByRole('button', { name: /Go to candidates/i });
    expect(skipBtn).toBeDisabled();

    resolveUpload?.({ request_id: 'req-123', status: 'queued' });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/requests/req-123');
    });
  });
});
