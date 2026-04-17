import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { test, expect } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const samples = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../backend/tests/data/e2e_multilingual_web_samples.json'),
    'utf-8'
  )
);

const apiBase = process.env.ACMG_E2E_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1';

async function createOrReuseBatch(request) {
  const response = await request.post(`${apiBase}/tasks/requests/web/crawl`, {
    data: {
      task_form: JSON.stringify({
        goal: 'PS3/BS3 evidence',
        disease: 'hereditary disease variant interpretation',
        country: 'MULTI',
        language: 'MULTI',
      }),
      urls: samples.map((sample) => sample.url),
      source: 'web',
      force_refresh: false,
    },
  });
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  return payload.request_id;
}

async function pollTerminal(request, requestId) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const response = await request.get(`${apiBase}/tasks/requests/${requestId}`);
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    if (payload.papers?.length === 10 && payload.papers.every((paper) => ['success', 'failed', 'partial_failed'].includes(String(paper.status)))) {
      return payload;
    }
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  throw new Error(`request ${requestId} did not finish in time`);
}

test('request page, document page, and graph page render real backend data for 10 samples', async ({ page, request }) => {
  const requestId = await createOrReuseBatch(request);
  const requestPayload = await pollTerminal(request, requestId);

  await page.goto(`/requests/${requestId}`);
  await expect(page.getByText(requestId)).toBeVisible();
  await expect(page.getByText(/Papers:\s*10/i)).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/paper_task_id:/i)).not.toBeVisible();
  await page.getByRole('button', { name: 'Details' }).first().click();
  await expect(page.getByText(/paper_task_id:/i)).toBeVisible();

  for (const paper of requestPayload.papers.filter((item) => item.status === 'success')) {
    await page.goto(`/documents/${paper.document_id}?paperTaskId=${paper.paper_task_id}`);
    await expect(page.getByTestId('document-source-panel')).not.toHaveText('—');
    await expect(page.getByTestId('document-target-panel')).not.toHaveText('—');
    await expect(page.getByTestId('document-evidence-json')).not.toHaveText('{}');

    const bundleResponse = await request.get(`${apiBase}/evidence/document/${paper.document_id}`);
    const bundle = (await bundleResponse.json()).data;
    const firstRecord = bundle.graph?.evidence_records?.find((record) => record.gene_symbol || record.variant_hgvs_c);
    if (!firstRecord) continue;

    await page.goto('/graph');
    if (firstRecord.gene_symbol) {
      await page.getByLabel(/Gene symbol/i).fill(firstRecord.gene_symbol);
    } else {
      await page.getByLabel(/Variant/i).fill(firstRecord.variant_hgvs_c);
    }
    await page.getByRole('button', { name: /Search graph/i }).click();
    await expect(page.getByTestId('graph-node-list')).not.toBeEmpty();
    await expect(page.getByTestId('graph-edge-list')).not.toBeEmpty();
  }
});
