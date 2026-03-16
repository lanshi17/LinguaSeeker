export type UploadValidationCode =
  | 'INPUT_INVALID'
  | 'FILE_TOO_LARGE'
  | 'FILE_TYPE_UNSUPPORTED'
  | 'FILE_DUPLICATE'
  | 'TOO_MANY_FILES'
  | 'TOTAL_SIZE_TOO_LARGE';

export type UploadValidationIssue = {
  code: UploadValidationCode;
  message: string;
};

export type UploadLimits = {
  maxFiles: number;
  maxSingleBytes: number;
  maxTotalBytes: number;
  allowedExtensions: string[];
};

export const DEFAULT_UPLOAD_LIMITS: UploadLimits = {
  maxFiles: 10,
  maxSingleBytes: 10 * 1024 * 1024,
  maxTotalBytes: 50 * 1024 * 1024,
  allowedExtensions: ['.pdf', '.docx']
};

function getFileExt(name: string) {
  const lower = name.toLowerCase();
  const idx = lower.lastIndexOf('.');
  if (idx < 0) return '';
  return lower.slice(idx);
}

export type UploadValidationResult = {
  ok: boolean;
  issues: UploadValidationIssue[];
};

export function validateUploadFiles(files: File[], limits: UploadLimits = DEFAULT_UPLOAD_LIMITS): UploadValidationResult {
  const issues: UploadValidationIssue[] = [];

  if (!Array.isArray(files)) {
    return { ok: false, issues: [{ code: 'INPUT_INVALID', message: 'Invalid files input' }] };
  }

  if (files.length === 0) {
    return { ok: false, issues: [{ code: 'INPUT_INVALID', message: 'Please select at least one file' }] };
  }

  if (files.length > limits.maxFiles) {
    issues.push({ code: 'TOO_MANY_FILES', message: `Max files: ${limits.maxFiles}` });
  }

  const seenNames = new Set<string>();
  let totalBytes = 0;

  for (const file of files) {
    const ext = getFileExt(file.name);
    if (!limits.allowedExtensions.includes(ext)) {
      issues.push({
        code: 'FILE_TYPE_UNSUPPORTED',
        message: `Unsupported file type: ${ext || '(no extension)'}`
      });
    }

    if (file.size > limits.maxSingleBytes) {
      issues.push({ code: 'FILE_TOO_LARGE', message: `Single file exceeds ${(limits.maxSingleBytes / 1024 / 1024).toFixed(0)}MB` });
    }

    totalBytes += file.size;

    const key = file.name.trim().toLowerCase();
    if (seenNames.has(key)) {
      issues.push({ code: 'FILE_DUPLICATE', message: `Duplicate file: ${file.name}` });
    }
    seenNames.add(key);
  }

  if (totalBytes > limits.maxTotalBytes) {
    issues.push({ code: 'TOTAL_SIZE_TOO_LARGE', message: `Total size exceeds ${(limits.maxTotalBytes / 1024 / 1024).toFixed(0)}MB` });
  }

  return { ok: issues.length === 0, issues };
}
