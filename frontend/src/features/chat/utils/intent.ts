export type ChatActionIntent =
  | "chat"
  | "search-evidence"
  | "start-pipeline"
  | "upload-pdf";

const UPLOAD_PATTERNS = [
  /\bupload\b/i,
  /\bpdf\b/i,
  /上传/,
  /本地/,
  /文件/,
];

const EXTRACTION_PATTERNS = [
  /\b(start|run)\b.*\bpipeline\b/i,
  /\b(analyze|analyse|extract)\b.*\b(paper|literature|evidence|document)\b/i,
  /\b(paper|literature|document)\b.*\b(extraction|extract)\b/i,
  /文献.*(提取|抽取|分析)/,
  /(证据|信息).*(提取|抽取)/,
  /(提取|抽取|分析).*文献/,
];

const SEARCH_PATTERNS = [
  /\b(search|query|lookup)\b.*\b(database|db|evidence)\b/i,
  /\b(existing|stored)\b.*\bevidence\b/i,
  /(查询|检索|搜索|查找).*(数据库|已有证据|现有证据|证据库|证据)/,
  /(数据库|证据库).*(查询|检索|搜索|查找)/,
];

function matchesAny(message: string, patterns: RegExp[]) {
  return patterns.some((pattern) => pattern.test(message));
}

export function detectChatActionIntent(message: string): ChatActionIntent {
  const normalized = message.trim();
  if (!normalized) {
    return "chat";
  }

  if (matchesAny(normalized, SEARCH_PATTERNS)) {
    return "search-evidence";
  }

  if (matchesAny(normalized, UPLOAD_PATTERNS)) {
    return "upload-pdf";
  }

  if (matchesAny(normalized, EXTRACTION_PATTERNS)) {
    return "start-pipeline";
  }

  return "chat";
}
