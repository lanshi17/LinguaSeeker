import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { EvidenceFieldsPanel } from './EvidenceFieldsPanel';

import type { EvidenceSearchData } from '../../types/evidence';

afterEach(cleanup);

const sampleRecord: EvidenceSearchData['evidence_records'] = [
  {
    evidence_id: 1,
    document_id: 'doc-uuid-1',
    gene_symbol: 'BRCA1',
    variant_hgvs_c: 'c.5382insC',
    variant_hgvs_p: 'p.Glu1730ArgfsTer63',
    evidence_strength: 'strong',
    evidence_classification: 'Pathogenic',
    overall_confidence: 92.5,
    is_valid: 'true',
    acmg_levels: ['PS3'],
    extracted_fields: {
      gene: {
        symbol: 'BRCA1',
        full_name: 'BRCA1 DNA repair associated',
        confidence: 95,
        evidence_quote: 'The BRCA1 gene variant was identified.',
      },
      variant: {
        hgvs_c: 'c.5382insC',
        hgvs_p: 'p.Glu1730ArgfsTer63',
        variant_type: 'frameshift',
        confidence: 90,
      },
      experiment_data: {
        assay_type: 'functional assay',
        method_description: 'Cell line assay',
        key_findings: ['Loss of function confirmed', 'Reduced protein stability'],
        confidence: 88,
      },
      disease_chpo: {
        disease_name: 'Hereditary breast cancer',
        omim_id: '604370',
        inheritance_pattern: 'AD',
        confidence: 85,
      },
    },
  },
];

describe('EvidenceFieldsPanel', () => {
  it('renders no-data message when data is null', () => {
    render(<EvidenceFieldsPanel data={null} />);
    expect(screen.getByText(/No evidence data available/i)).toBeInTheDocument();
  });

  it('renders no-records message when evidence_records is empty', () => {
    render(<EvidenceFieldsPanel data={{ evidence_records: [], total_evidence: 0 }} />);
    expect(screen.getByText(/No evidence records found/i)).toBeInTheDocument();
  });

  it('renders record header with gene symbol and classification', () => {
    render(<EvidenceFieldsPanel data={{ evidence_records: sampleRecord }} />);
    expect(screen.getByText('BRCA1')).toBeInTheDocument();
    expect(screen.getByText('Pathogenic')).toBeInTheDocument();
    expect(screen.getByText('strong')).toBeInTheDocument();
    expect(screen.getByText(/92\.5/)).toBeInTheDocument();
    expect(screen.getByText(/✓ Valid/)).toBeInTheDocument();
  });

  it('expands record to show extracted fields on click', async () => {
    render(<EvidenceFieldsPanel data={{ evidence_records: sampleRecord }} />);

    // Initially collapsed — extracted fields are not visible
    expect(screen.queryByText('Extracted Fields')).not.toBeInTheDocument();

    // Click to expand
    const button = screen.getByRole('button');
    fireEvent.click(button);

    expect(screen.getByText('Extracted Fields')).toBeInTheDocument();
    // Gene section
    expect(screen.getByText('BRCA1 DNA repair associated')).toBeInTheDocument();
    // Experiment section
    expect(screen.getByText('functional assay')).toBeInTheDocument();
    expect(screen.getByText('Loss of function confirmed')).toBeInTheDocument();
    // Disease section
    expect(screen.getByText('Hereditary breast cancer')).toBeInTheDocument();
  });

  it('shows "Not extracted" list for missing fields', async () => {
    render(<EvidenceFieldsPanel data={{ evidence_records: sampleRecord }} />);
    const button = screen.getByRole('button');
    fireEvent.click(button);

    // Only gene, variant, experiment_data, disease_chpo are set → rest should appear in "Not extracted"
    expect(screen.getByText(/Not extracted:/i)).toBeInTheDocument();
    expect(screen.getByText(/Transcript/i)).toBeInTheDocument();
  });

  it('shows record count summary', () => {
    render(
      <EvidenceFieldsPanel
        data={{ evidence_records: sampleRecord, document_count: 1, total_evidence: 1 }}
      />
    );
    expect(screen.getByText(/1 record from 1 document/i)).toBeInTheDocument();
  });

  it('handles record without extracted_fields gracefully', async () => {
    const noFieldsRecord = [{ evidence_id: 2, gene_symbol: 'TP53', is_valid: 'false' }];
    render(<EvidenceFieldsPanel data={{ evidence_records: noFieldsRecord }} />);

    const button = screen.getByRole('button');
    fireEvent.click(button);

    expect(screen.getByText(/No extracted fields available/i)).toBeInTheDocument();
  });
});
