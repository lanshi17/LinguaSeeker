import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, RouterProvider } from 'react-router-dom';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { router } from '../../../router';
import { useTaskFlowStore } from '../../../store/useTaskFlowStore';
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

function renderAgentCreateRoute(initialPath = '/tasks/agent-create') {
  window.history.pushState({}, 'Test page', initialPath);
  return render(<RouterProvider router={router} />);
}

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
    configurable: true,
    value: vi.fn(),
  });
});

afterAll(() => {
  Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo');
});

describe('AgentTaskCreatePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.pushState({}, 'Test page', '/');
    useTaskFlowStore.setState({
      entryMode: null,
    });
    useWorkflowStore.getState().reset();
  });

  afterEach(() => {
    cleanup();
    useTaskFlowStore.setState({
      entryMode: null,
    });
    useWorkflowStore.getState().reset();
  });

  it('renders entry mode fallback and disconnected request/task states with empty workflow copy', async () => {
    const { AgentTaskCreatePage } = await import('../agent-task-create-page');

    renderPage(AgentTaskCreatePage);

    expect(screen.getByRole('heading', { name: /Agent-driven task creation/i })).toBeInTheDocument();
    expect(screen.getByText(/Entry mode: not set/i)).toBeInTheDocument();
    expect(screen.getByText(/Request connection: disconnected/i)).toBeInTheDocument();
    expect(screen.getByText(/Task connection: disconnected/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Conversation/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Workflow status/i })).toBeInTheDocument();
    expect(screen.getByText(/No workflow stream connected yet/i)).toBeInTheDocument();
  });

  it('renders entry mode framing, separate connection labels, and shared timelines when workflow data exists', async () => {
    useTaskFlowStore.setState({
      entryMode: 'documents',
    });
    useWorkflowStore.setState({
      requestConnection: { requestId: 'req-123', connected: true },
      taskConnection: { taskId: 'task-456', connected: true },
      requestTimeline: [
        { id: 'queued', label: 'Queued', status: 'completed' },
        { id: 'running', label: 'Running', status: 'running', description: 'Request in progress', progress: 40 },
        { id: 'success', label: 'Completed', status: 'pending' },
      ],
      taskTimeline: [
        { id: 'queued', label: 'Queued', status: 'completed' },
        { id: 'running', label: 'Running', status: 'running', description: 'Task in progress', progress: 70 },
        { id: 'success', label: 'Completed', status: 'pending' },
      ],
    });

    const { AgentTaskCreatePage } = await import('../agent-task-create-page');

    renderPage(AgentTaskCreatePage);

    expect(screen.getByText(/Entry mode: documents/i)).toBeInTheDocument();
    expect(screen.getByText(/Request connection: connected/i)).toBeInTheDocument();
    expect(screen.getByText(/Task connection: connected/i)).toBeInTheDocument();
    expect(screen.getByText('Request')).toBeInTheDocument();
    expect(screen.getByText('Task')).toBeInTheDocument();
    expect(screen.getByText(/Request in progress/i)).toBeInTheDocument();
    expect(screen.getByText(/Task in progress/i)).toBeInTheDocument();
    expect(screen.getByText(/40%/i)).toBeInTheDocument();
    expect(screen.getByText(/70%/i)).toBeInTheDocument();
  });

  it('navigates to task form flow when opening the detailed editor', async () => {
    const { AgentTaskCreatePage } = await import('../agent-task-create-page');

    renderPage(AgentTaskCreatePage);

    fireEvent.click(screen.getByRole('button', { name: /Open task form flow/i }));

    expect(mockNavigate).toHaveBeenCalledWith('/tasks/new');
  });

  it('renders the agent workspace route at /tasks/agent-create', async () => {
    renderAgentCreateRoute();

    expect(await screen.findByRole('heading', { name: /Agent-driven task creation/i })).toBeInTheDocument();
    expect(screen.getByTestId('agent-task-create-page')).toBeInTheDocument();
  });

  it('redirects the root entry path to the agent workspace route', async () => {
    renderAgentCreateRoute('/');

    await screen.findByRole('heading', { name: /Agent-driven task creation/i });

    expect(router.state.location.pathname).toBe('/tasks/agent-create');
    expect(screen.getByTestId('agent-task-create-page')).toBeInTheDocument();
  });
});
