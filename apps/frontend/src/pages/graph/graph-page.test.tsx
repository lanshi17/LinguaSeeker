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
  it('renders returned node labels and relationships in dedicated graph lists', async () => {
    vi.mocked(searchEvidence).mockResolvedValue({
      code: 0,
      message: 'ok',
      data: {
        nodes: [{ id: 'g1', type: 'gene', label: 'BRCA1' }],
        edges: [{ source: 'g1', target: 'd1', relationship: 'RELATED_TO' }],
        total_evidence: 2,
        document_count: 1,
        evidence_records: [{ document_id: 'doc-1' }],
      },
    });

    render(<GraphPage />);
    fireEvent.change(screen.getByLabelText(/Gene symbol/i), { target: { value: 'BRCA1' } });
    fireEvent.click(screen.getByRole('button', { name: /Search graph/i }));

    await waitFor(() => expect(searchEvidence).toHaveBeenCalledWith({ gene_symbol: 'BRCA1' }));
    expect(await screen.findByTestId('graph-node-list')).toHaveTextContent('BRCA1');
    expect(screen.getByTestId('graph-edge-list')).toHaveTextContent('RELATED_TO');
  });
});
