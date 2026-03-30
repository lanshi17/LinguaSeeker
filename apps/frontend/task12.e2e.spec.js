import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  const requestPayload = {
    request_id: 'req-e2e-123',
    status: 'running',
    papers: [
      { paper_task_id: 'paper-1', status: 'running', filename: 'paper-1.pdf', document_id: 'doc-1', error_code: null, duplicate_of: null },
      { paper_task_id: 'paper-2', status: 'success', filename: 'paper-2.pdf', document_id: 'doc-2', error_code: null, duplicate_of: null },
    ],
  };

  const evidencePayload = {
    data: {
      source_lang: 'en',
      target_lang: 'zh',
      segments: [{ id: 'seg-1', source_text: 'Source sentence', target_text: '目标句子' }],
      judgments: [{ rule_code: 'PS3', strength: 'moderate', conclusion: 'Supports pathogenicity' }],
    },
  };

  const candidatesPayload = {
    request_id: 'req-e2e-123',
    candidates: [
      { pmid: '1001', title: 'Candidate one', journal: 'Nature', pub_date: '2024-01-01' },
      { pmid: '1002', title: 'Candidate two', journal: 'Science', pub_date: '2024-02-01' },
    ],
  };

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new globalThis.URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === 'GET' && path === '/api/v1/tasks/requests/req-e2e-123') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(requestPayload) });
      return;
    }
    if (method === 'GET' && path === '/api/v1/logs/reissue') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ log_link: 'https://example.com/logs/req-e2e-123' }) });
      return;
    }
    if (method === 'GET' && path === '/api/v1/evidence/document/doc-1') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(evidencePayload) });
      return;
    }
    if (method === 'GET' && path === '/api/v1/evidence/document/doc-2') {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'doc-2 failed' }) });
      return;
    }
    if (method === 'POST' && path === '/api/v1/tasks/requests/pubmed/candidates') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(candidatesPayload) });
      return;
    }
    if (method === 'POST' && path === '/api/v1/tasks/requests/pubmed/submit') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ request_id: 'req-e2e-123', status: 'queued' }) });
      return;
    }

    await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: `Unhandled route: ${method} ${path}` }) });
  });
});

test('request monitor expands details', async ({ page }) => {
  await page.goto('/requests/req-e2e-123');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Details' }).first().click();
  await expect(page.getByText(/paper_task_id: paper-1/i)).toBeVisible();
});

test('request export auto-selects doc-1 and shows toast on doc-2 error', async ({ page }) => {
  await page.goto('/requests/req-e2e-123/export');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('select')).toHaveValue('doc-1');
  await expect(page.locator('section').first().getByText('Source sentence', { exact: true })).toBeVisible();
  await page.locator('select').selectOption('doc-2');
  await expect(page.getByText(/Evidence load failed/i)).toBeVisible();
});

test('pubmed candidates blocks without in-memory task flow state', async ({ page }) => {
  await page.goto('/tasks/pubmed/candidates');
  await page.waitForLoadState('networkidle');
  await expect(page.getByText(/Confirmation state or task form not found/i)).toBeVisible();
});
