import { describe, expect, it } from 'vitest';

import { DEFAULT_UPLOAD_LIMITS, validateUploadFiles } from './validation';

function makeFile(name: string, sizeBytes: number) {
  const blob = new Blob([new Uint8Array(sizeBytes)]);
  return new File([blob], name, { type: 'application/octet-stream' });
}

describe('validateUploadFiles', () => {
  it('rejects empty list', () => {
    const res = validateUploadFiles([]);
    expect(res.ok).toBe(false);
  });

  it('accepts a single pdf under limits', () => {
    const res = validateUploadFiles([makeFile('a.pdf', 1024)]);
    expect(res.ok).toBe(true);
  });

  it('rejects unsupported extension', () => {
    const res = validateUploadFiles([makeFile('a.txt', 10)]);
    expect(res.ok).toBe(false);
    expect(res.issues.some((i) => i.code === 'FILE_TYPE_UNSUPPORTED')).toBe(true);
  });

  it('rejects duplicates by name', () => {
    const res = validateUploadFiles([makeFile('a.pdf', 10), makeFile('A.PDF', 12)]);
    expect(res.ok).toBe(false);
    expect(res.issues.some((i) => i.code === 'FILE_DUPLICATE')).toBe(true);
  });

  it('rejects oversize single file (using smaller test limits)', () => {
    const limits = { ...DEFAULT_UPLOAD_LIMITS, maxSingleBytes: 1000 };
    const res = validateUploadFiles([makeFile('a.pdf', 1001)], limits);
    expect(res.ok).toBe(false);
    expect(res.issues.some((i) => i.code === 'FILE_TOO_LARGE')).toBe(true);
  });

  it('rejects total size too large (using smaller test limits)', () => {
    const limits = { ...DEFAULT_UPLOAD_LIMITS, maxTotalBytes: 1000 };
    const res = validateUploadFiles([makeFile('a.pdf', 600), makeFile('b.pdf', 600)], limits);
    expect(res.ok).toBe(false);
    expect(res.issues.some((i) => i.code === 'TOTAL_SIZE_TOO_LARGE')).toBe(true);
  });
});
