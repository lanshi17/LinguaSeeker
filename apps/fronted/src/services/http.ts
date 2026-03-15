import { getApiBaseUrl } from '../config/env';

export type ApiErrorInfo = {
  status: number;
  message: string;
  detail?: string;
  responseBody?: unknown;
};

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail?: string;
  public readonly responseBody?: unknown;

  constructor(info: ApiErrorInfo) {
    super(info.message);
    this.name = 'ApiError';
    this.status = info.status;
    this.detail = info.detail;
    this.responseBody = info.responseBody;
  }
}

async function readJsonBodySafe(res: Response): Promise<unknown | null> {
  const contentType = res.headers.get('content-type') ?? '';
  if (!contentType.toLowerCase().includes('application/json')) {
    return null;
  }
  try {
    return await res.json();
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown JSON parse error';
    throw new ApiError({ status: res.status, message: `Failed to parse JSON response: ${msg}` });
  }
}

function buildUrl(path: string) {
  const base = getApiBaseUrl();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

type RequestOptions = {
  signal?: AbortSignal;
  headers?: Record<string, string>;
};

export async function requestJson<T>(
  path: string,
  init: Omit<RequestInit, 'body'> & { body?: unknown },
  options: RequestOptions = {}
): Promise<T> {
  const url = buildUrl(path);
  const res = await fetch(url, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...(options.headers ?? {}),
      ...(init.headers ?? {})
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    signal: options.signal
  });

  const body = await readJsonBodySafe(res);
  if (body === null) {
    throw new ApiError({ status: res.status, message: 'Expected JSON response but got none' });
  }
  if (!res.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body && typeof (body as { detail?: unknown }).detail === 'string'
        ? (body as { detail: string }).detail
        : undefined;
    throw new ApiError({ status: res.status, message: `Request failed (${res.status})`, detail, responseBody: body });
  }

  return body as T;
}

export async function requestFormData<T>(
  path: string,
  init: Omit<RequestInit, 'body'> & { body: FormData },
  options: RequestOptions = {}
): Promise<T> {
  const url = buildUrl(path);
  const res = await fetch(url, {
    ...init,
    headers: {
      ...(options.headers ?? {}),
      ...(init.headers ?? {})
    },
    body: init.body,
    signal: options.signal
  });

  const body = await readJsonBodySafe(res);
  if (body === null) {
    throw new ApiError({ status: res.status, message: 'Expected JSON response but got none' });
  }
  if (!res.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body && typeof (body as { detail?: unknown }).detail === 'string'
        ? (body as { detail: string }).detail
        : undefined;
    throw new ApiError({ status: res.status, message: `Request failed (${res.status})`, detail, responseBody: body });
  }

  return body as T;
}

export async function requestGetJson<T>(path: string, options: RequestOptions = {}) {
  return requestJson<T>(path, { method: 'GET' }, options);
}
