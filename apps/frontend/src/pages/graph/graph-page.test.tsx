import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/api', () => ({
  getEvidenceGraphStats: vi.fn(),
  resyncEvidenceDocument: vi.fn(),
  searchEvidence: vi.fn(),
}));

import { GraphPage } from './graph-page';
import { searchEvidence } from '../../services/api';

beforeEach(() => vi.clearAllMocks());

describe('GraphPage', () => {
  it('submits graph search filters and renders node/edge counts', async () => {
    vi.mocked(searchEvidence).mockResolvedValue({
      code: 0,
      message: 'ok',
      data: {
        nodes: [{ id: 'g1', type: 'gene', label: 'BRCA1' }],
        edges: [{ source: 'g1', target: 'd1', relationship: 'RELATED_TO' }],
        total_evidence: 2,
        document_count: 1,
      },
    });

    render(<GraphPage />);

    fireEvent.change(screen.getByLabelText(/Gene symbol/i), { target: { value: 'BRCA1' } });
    fireEvent.click(screen.getByRole('button', { name: /Search graph/i }));

    await waitFor(() => expect(searchEvidence).toHaveBeenCalledWith({ gene_symbol: 'BRCA1' }));
    expect(await screen.findByText(/Nodes: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Edges: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Evidence: 2/i)).toBeInTheDocument();
  });
});
