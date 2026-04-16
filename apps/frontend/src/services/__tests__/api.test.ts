import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../http', () => ({
  requestGetJson: vi.fn(),
  requestJson: vi.fn(),
  requestFormData: vi.fn(),
}));

import { requestJson } from '../http';
import { searchEvidence, webCrawlSubmit } from '../api';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('api route helpers', () => {
  it('posts web crawl submissions to the web branch endpoint', async () => {
    vi.mocked(requestJson).mockResolvedValue({ request_id: 'req-1', status: 'queued' });

    await webCrawlSubmit({
      task_form: 'Find PS3 evidence',
      urls: ['https://example.com/paper'],
      source: 'web',
      force_refresh: false,
    });

    expect(requestJson).toHaveBeenCalledWith(
      '/tasks/requests/web/crawl',
      expect.objectContaining({ method: 'POST' }),
      expect.any(Object)
    );
  });

  it('posts graph search filters to the evidence search endpoint', async () => {
    vi.mocked(requestJson).mockResolvedValue({ code: 0, message: 'ok', data: { nodes: [], edges: [] } });

    await searchEvidence({ gene_symbol: 'BRCA1' });

    expect(requestJson).toHaveBeenCalledWith(
      '/evidence/search',
      expect.objectContaining({ method: 'POST', body: { gene_symbol: 'BRCA1' } }),
      expect.any(Object)
    );
  });
});
