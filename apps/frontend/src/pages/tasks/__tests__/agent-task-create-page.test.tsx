import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkflowStore } from '../../../store/useWorkflowStore';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderPage(Component: React.ComponentType) {
  return render(
    <MemoryRouter>
      <Component />
    </MemoryRouter>
  );
}

describe('AgentTaskCreatePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkflowStore.getState().reset();
  });

  afterEach(() => {
    cleanup();
    useWorkflowStore.getState().reset();
  });

  it('renders conversation and workflow sections with empty-state copy', async () => {
    const { AgentTaskCreatePage } = await import('../agent-task-create-page');

    renderPage(AgentTaskCreatePage);

    expect(screen.getByRole('heading', { name: /Agent-driven task creation/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Conversation/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Workflow status/i })).toBeInTheDocument();
    expect(screen.getByText(/No workflow stream connected yet/i)).toBeInTheDocument();
  });

  it('navigates to task form flow when opening the detailed editor', async () => {
    const { AgentTaskCreatePage } = await import('../agent-task-create-page');

    renderPage(AgentTaskCreatePage);

    fireEvent.click(screen.getByRole('button', { name: /Open task form flow/i }));

    expect(mockNavigate).toHaveBeenCalledWith('/tasks/new');
  });
});
