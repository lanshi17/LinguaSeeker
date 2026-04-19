import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { GraphPage } from '../graph-page';
import * as api from '../../../services/api';

vi.mock('../../../services/api', () => ({
  searchEvidenceGraph: vi.fn(),
  getEvidenceGraphStats: vi.fn(),
  resyncEvidenceDocument: vi.fn(),
}));

describe('GraphPage', () => {
  it('renders graph search results and opens a document link from a node', async () => {
    vi.mocked(api.searchEvidenceGraph).mockResolvedValue({
      code: 0,
      message: 'ok',
      data: {
        nodes: [{ id: 'doc:1', type: 'document', label: 'Fabry case report' }],
        edges: [],
        evidence_records: [],
        document_count: 1,
        total_evidence: 1,
      },
    });

    render(
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/GLA:c\.92C>A/i), { target: { value: 'GLA:c.92C>A' } });
    fireEvent.click(screen.getByRole('button', { name: /Search graph/i }));

    expect(await screen.findByText(/Fabry case report/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open document/i })).toHaveAttribute('href', '/documents/1');
  });
});
