import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import type { WorkflowTimelineStep } from '../../types/stream';
import { WorkflowTimeline } from './workflow-timeline';

function renderTimeline(options?: {
  steps?: WorkflowTimelineStep[];
  emptyMessage?: string;
  title?: string;
}) {
  return render(
    <WorkflowTimeline
      title={options?.title}
      steps={options?.steps ?? []}
      emptyMessage={options?.emptyMessage}
    />
  );
}

afterEach(() => {
  cleanup();
});

describe('WorkflowTimeline', () => {
  it('renders configurable empty-state copy when there are no steps', () => {
    renderTimeline({ emptyMessage: 'No task data yet' });

    expect(screen.getByText('No task data yet')).toBeInTheDocument();
  });

  it('renders a running step with description and progress', () => {
    renderTimeline({
      steps: [
        { id: 'queued', label: 'Queued', status: 'completed' },
        {
          id: 'running',
          label: 'Running',
          status: 'running',
          description: 'Parsing PDF',
          progress: 40,
        },
      ],
    });

    expect(screen.getByText('Queued')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Parsing PDF')).toBeInTheDocument();
    expect(screen.getByText('40%')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
  });

  it('renders custom step ids with optional title and pending status', () => {
    renderTimeline({
      title: 'Workflow timeline',
      steps: [{ id: 'custom-step', label: 'Waiting', status: 'pending' }],
    });

    expect(screen.getByText('Workflow timeline')).toBeInTheDocument();
    expect(screen.getByText('Waiting')).toBeInTheDocument();
    expect(screen.getByText('pending')).toBeInTheDocument();
  });

  it('renders an error step status and description', () => {
    renderTimeline({
      steps: [
        {
          id: 'running',
          label: 'Running',
          status: 'error',
          description: 'Parser failed',
        },
      ],
    });

    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('error')).toBeInTheDocument();
    expect(screen.getByText('Parser failed')).toBeInTheDocument();
  });
});
