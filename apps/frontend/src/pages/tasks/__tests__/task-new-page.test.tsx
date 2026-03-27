import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { TaskNewPage } from '../task-new-page';
import { useTaskFlowStore } from '../../../store/useTaskFlowStore';
import * as api from '../../../services/api';

vi.mock('../../../services/api', () => ({
  confirmTaskForm: vi.fn(),
  uploadTaskRequest: vi.fn(),
  interactionStart: vi.fn(),
  interactionRespond: vi.fn(),
}));

describe('TaskNewPage', () => {
  let originalScrollTo: typeof Element.prototype.scrollTo;

  beforeAll(() => {
    originalScrollTo = Element.prototype.scrollTo;
    Element.prototype.scrollTo = vi.fn();
  });

  afterAll(() => {
    Element.prototype.scrollTo = originalScrollTo;
  });

  beforeEach(() => {
    vi.clearAllMocks();
    useTaskFlowStore.setState({
      taskForm: null,
      interactionSessionId: null,
      interactionRound: 0,
      entryMode: 'documents',
      confirmedRequestId: null,
      taskFormPayload: null,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('a) shows clarification round counter', () => {
    render(
      <BrowserRouter>
        <TaskNewPage />
      </BrowserRouter>
    );
    expect(screen.getByText(/Clarification rounds: 0\/2/i)).toBeInTheDocument();
  });

  it('b) stops further clarification at second round', () => {
    useTaskFlowStore.setState({
      interactionRound: 2,
      interactionSessionId: 'sess-123'
    });
    render(
      <BrowserRouter>
        <TaskNewPage />
      </BrowserRouter>
    );
    
    expect(screen.getByText(/Clarification rounds: 2\/2/i)).toBeInTheDocument();
    
    const sendBtn = screen.queryByRole('button', { name: /Send/i });
    if (sendBtn) {
      expect(sendBtn).toBeDisabled();
    }

    const composer = screen.getByRole('textbox', { name: /澄清回答/i });
    expect(composer).toBeDisabled();
    
    expect(screen.getByText(/Max clarification rounds reached/i)).toBeInTheDocument();
  });

  it('c) sets defaults for auto-generated task form', () => {
    render(
      <BrowserRouter>
        <TaskNewPage />
      </BrowserRouter>
    );
    
    expect(screen.getByRole('textbox', { name: /Country/i })).toHaveValue('不限');
    expect(screen.getByRole('textbox', { name: /Language/i })).toHaveValue('auto');
  });

  it('d) shows generated task-form fields and allows e) editing them', () => {
    useTaskFlowStore.setState({
      taskForm: {
        goal: 'Original Goal',
        disease: 'Original Disease',
        country: 'US',
        language: 'en'
      }
    });

    render(
      <BrowserRouter>
        <TaskNewPage />
      </BrowserRouter>
    );

    const goalInput = screen.getByRole('textbox', { name: /Goal/i });
    expect(goalInput).toHaveValue('Original Goal');

    fireEvent.change(goalInput, { target: { value: 'Updated Goal' } });
    expect(goalInput).toHaveValue('Updated Goal');
  });

  it('f) disables branch zone initially, then enables it when confirmedRequestId is present', async () => {
    useTaskFlowStore.setState({
      taskForm: { goal: 'a', disease: 'b', country: 'c', language: 'd' },
      confirmedRequestId: null
    });

    vi.mocked(api.confirmTaskForm).mockResolvedValue({
      request_id: 'req-123',
      confirmed: true
    });

    render(
      <BrowserRouter>
        <TaskNewPage />
      </BrowserRouter>
    );

    const submitBtn = screen.getByRole('button', { name: /Submit upload/i });
    expect(submitBtn).toBeDisabled();

    expect(screen.queryByRole('link', { name: /Go to candidates/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Confirmation required/i)).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: /Confirm Task Form/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /Go to candidates/i })).toBeInTheDocument();
    });
    
    expect(screen.queryByText(/Confirmation required/i)).not.toBeInTheDocument();
  });
});