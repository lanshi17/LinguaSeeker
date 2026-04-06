import { describe, expect, it } from 'vitest';

import { normalizePaperResult } from './normalizePaperResult';

describe('normalizePaperResult', () => {
  it('normalizes duplicate/fulltext flags and judgment statuses', () => {
    const normalized = normalizePaperResult({
      paper_task_id: 'paper-1',
      request_id: 'req-1',
      document_id: 'doc-1',
      status: 'success',
      workflow_status: 'COMPLETED',
      processing_steps: {
        classification: { status: 'COMPLETED' },
        adjudication: { status: 'COMPLETED' },
      },
      warning_codes: ['FULLTEXT_UNAVAILABLE'],
      trace_chain: {
        steps: {
          classification: { status: 'COMPLETED', outcome: 'success' },
          adjudication: { status: 'COMPLETED', outcome: 'success' },
        },
      },
      fulltext_unavailable: true,
      result_payload: {
        graph_sync_result: { neo4j_ok: true },
      },
      parsing_metadata: { parser_backend: 'mineru' },
      duplicate_of: 'paper-0',
    });

    expect(normalized.badges).toContain('Duplicate reuse');
    expect(normalized.badges).toContain('Fulltext unavailable');
    expect(normalized.classification.title).toBe('ACMG classification');
    expect(normalized.adjudication.title).toBe('Expert adjudication');
    expect(normalized.classification.graphSyncOk).toBe(true);
  });
});
