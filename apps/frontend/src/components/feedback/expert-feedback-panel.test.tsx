import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ExpertFeedbackPanel } from './expert-feedback-panel';

describe('ExpertFeedbackPanel', () => {
  it('renders heading, helper copy, tone styles, and inline actions', () => {
    const onAction = vi.fn();

    render(
      <ExpertFeedbackPanel
        items={[
          { tone: 'info', text: 'Confirm the task form to lock the request id before branching.', action: 'confirm_now' },
          { tone: 'warning', text: 'Clarification rounds reached limit; restart clarification if the task form is still missing.' },
          { tone: 'success', text: 'Files selected (2). Submit upload when ready.' },
        ]}
        onAction={onAction}
      />
    );

    expect(screen.getByRole('heading', { name: 'Expert feedback' })).toBeInTheDocument();
    expect(screen.getByText('Plan-aligned review hints before upload/candidate branching.')).toBeInTheDocument();

    const confirmButton = screen.getByRole('button', { name: 'Confirm now' });
    fireEvent.click(confirmButton);

    expect(onAction).toHaveBeenCalledWith('confirm_now');
    expect(screen.getByText('Clarification rounds reached limit; restart clarification if the task form is still missing.')).toHaveStyle({ color: '#ad6800' });
    expect(screen.getByText('Files selected (2). Submit upload when ready.')).toHaveStyle({ color: '#237804' });
  });

  it('disables inline actions when busy', () => {
    render(
      <ExpertFeedbackPanel
        busy
        items={[
          { tone: 'info', text: 'Request is confirmed. You can upload files or continue to PubMed candidates.', action: 'go_candidates' },
        ]}
        onAction={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Open candidates shortcut' })).toBeDisabled();
  });
});
