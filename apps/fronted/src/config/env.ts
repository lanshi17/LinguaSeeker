function normalizeBaseUrl(url: string) {
  const trimmed = url.trim();
  if (trimmed.length === 0) return '/api/v1';
  return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed;
}

export function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  return normalizeBaseUrl(typeof envUrl === 'string' ? envUrl : '/api/v1');
}
