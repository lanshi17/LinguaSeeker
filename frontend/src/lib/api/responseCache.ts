import type {
  AxiosAdapter,
  AxiosResponse,
  InternalAxiosRequestConfig,
  RawAxiosResponseHeaders,
} from "axios";

export interface ResponseCacheRequestOptions {
  enabled?: boolean;
  ttlMs?: number;
}

type ResponseCacheConfig = InternalAxiosRequestConfig & {
  responseCache?: ResponseCacheRequestOptions;
};

interface ApiResponseCacheOptions {
  enabled?: boolean;
  ttlMs?: number;
  maxEntries?: number;
  maxEntryBytes?: number;
  now?: () => number;
  storage?: Storage | null;
  uncachedPathPatterns?: RegExp[];
}

interface CachedResponseRecord {
  version: 1;
  key: string;
  storedAt: number;
  expiresAt: number;
  status: number;
  statusText: string;
  headers: RawAxiosResponseHeaders;
  data: unknown;
}

interface CacheIndexEntry {
  key: string;
  storageKey: string;
  storedAt: number;
}

const CACHE_VERSION = 1;
const DEFAULT_TTL_MS = 5 * 60_000;
const DEFAULT_MAX_ENTRIES = 80;
const DEFAULT_MAX_ENTRY_BYTES = 512 * 1024;
const CACHE_PREFIX = "lingua-seeker:api-response-cache:v1";
const INDEX_STORAGE_KEY = `${CACHE_PREFIX}:index`;
const ENTRY_STORAGE_PREFIX = `${CACHE_PREFIX}:entry`;

const DEFAULT_UNCACHED_PATH_PATTERNS = [
  /^\/?pipeline(?:\/|$)/,
  /^\/?chat(?:\/|$)/,
  /^\/?delta-audit(?:\/|$)/,
  /^\/?evidence\/groups\/detail(?:\/|$)/,
  /\/annotations(?:\/|$)/,
];

class ApiResponseCache {
  private readonly memory = new Map<string, CachedResponseRecord>();
  private readonly enabled: boolean;
  private readonly ttlMs: number;
  private readonly maxEntries: number;
  private readonly maxEntryBytes: number;
  private readonly now: () => number;
  private readonly storage: Storage | null;
  private readonly uncachedPathPatterns: RegExp[];

  constructor(options: ApiResponseCacheOptions = {}) {
    this.enabled = options.enabled ?? true;
    this.ttlMs = options.ttlMs ?? DEFAULT_TTL_MS;
    this.maxEntries = options.maxEntries ?? DEFAULT_MAX_ENTRIES;
    this.maxEntryBytes = options.maxEntryBytes ?? DEFAULT_MAX_ENTRY_BYTES;
    this.now = options.now ?? Date.now;
    this.storage = options.storage === undefined ? getBrowserStorage() : options.storage;
    this.uncachedPathPatterns =
      options.uncachedPathPatterns ?? DEFAULT_UNCACHED_PATH_PATTERNS;
  }

  get(config: InternalAxiosRequestConfig): AxiosResponse | null {
    if (!this.isCacheableRequest(config)) return null;

    const key = buildRequestCacheKey(config);
    const storageRecord = this.readFromStorage(key);
    if (storageRecord) {
      this.memory.set(key, storageRecord);
      return recordToResponse(storageRecord, config);
    }

    const memoryRecord = this.memory.get(key);
    if (memoryRecord) {
      if (this.isFresh(memoryRecord)) {
        return recordToResponse(memoryRecord, config);
      }
      this.delete(key);
    }
    return null;
  }

  set(config: InternalAxiosRequestConfig, response: AxiosResponse): void {
    if (!this.isCacheableRequest(config) || !isCacheableResponse(response)) return;

    const key = buildRequestCacheKey(config);
    const now = this.now();
    const record: CachedResponseRecord = {
      version: CACHE_VERSION,
      key,
      storedAt: now,
      expiresAt: now + (responseCacheOptions(config)?.ttlMs ?? this.ttlMs),
      status: response.status,
      statusText: response.statusText,
      headers: headersToRecord(response.headers),
      data: response.data,
    };

    const serialized = safeJsonStringify(record);
    if (!serialized || serialized.length > this.maxEntryBytes) return;

    this.memory.set(key, record);
    if (!this.storage) {
      this.pruneMemory();
      return;
    }

    const storageKey = storageKeyFor(key);
    try {
      this.storage.setItem(storageKey, serialized);
      this.writeIndexEntry({ key, storageKey, storedAt: now });
      this.pruneStorage();
    } catch {
      this.storage.removeItem(storageKey);
    }
  }

  clear(): void {
    this.memory.clear();
    if (!this.storage) return;

    for (const entry of this.readIndex()) {
      this.storage.removeItem(entry.storageKey);
    }
    this.storage.removeItem(INDEX_STORAGE_KEY);
  }

  isMutation(config: InternalAxiosRequestConfig): boolean {
    const method = (config.method ?? "get").toLowerCase();
    return !["get", "head", "options"].includes(method);
  }

  private isCacheableRequest(config: InternalAxiosRequestConfig): boolean {
    if (!this.enabled) return false;
    if (responseCacheOptions(config)?.enabled === false) return false;

    const method = (config.method ?? "get").toLowerCase();
    if (method !== "get" && method !== "head") return false;

    const responseType = config.responseType;
    if (
      responseType &&
      !["json", "text"].includes(String(responseType).toLowerCase())
    ) {
      return false;
    }

    if (requestHeaderIncludes(config, "cache-control", "no-store")) {
      return false;
    }

    const path = normalizePath(config.url ?? "");
    return !this.uncachedPathPatterns.some((pattern) => pattern.test(path));
  }

  private readFromStorage(key: string): CachedResponseRecord | null {
    if (!this.storage) return null;

    const storageKey = storageKeyFor(key);
    try {
      const raw = this.storage.getItem(storageKey);
      if (!raw) return null;

      const parsed = JSON.parse(raw) as Partial<CachedResponseRecord>;
      if (!isRecordForKey(parsed, key)) {
        this.storage.removeItem(storageKey);
        return null;
      }
      if (!this.isFresh(parsed)) {
        this.delete(key);
        return null;
      }
      return parsed;
    } catch {
      this.storage.removeItem(storageKey);
      return null;
    }
  }

  private delete(key: string): void {
    this.memory.delete(key);
    if (!this.storage) return;

    const storageKey = storageKeyFor(key);
    this.storage.removeItem(storageKey);
    this.writeIndex(this.readIndex().filter((entry) => entry.key !== key));
  }

  private isFresh(record: Pick<CachedResponseRecord, "expiresAt">): boolean {
    return record.expiresAt > this.now();
  }

  private pruneMemory(): void {
    if (this.memory.size <= this.maxEntries) return;

    const entries = [...this.memory.entries()].sort(
      (left, right) => left[1].storedAt - right[1].storedAt,
    );
    for (const [key] of entries.slice(0, entries.length - this.maxEntries)) {
      this.memory.delete(key);
    }
  }

  private pruneStorage(): void {
    if (!this.storage) return;

    const freshEntries = this.readIndex()
      .filter((entry) => {
        const record = this.readFromStorage(entry.key);
        return record !== null;
      })
      .sort((left, right) => right.storedAt - left.storedAt);

    for (const entry of freshEntries.slice(this.maxEntries)) {
      this.storage.removeItem(entry.storageKey);
      this.memory.delete(entry.key);
    }

    this.writeIndex(freshEntries.slice(0, this.maxEntries));
    this.pruneMemory();
  }

  private readIndex(): CacheIndexEntry[] {
    if (!this.storage) return [];

    try {
      const raw = this.storage.getItem(INDEX_STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.filter(isCacheIndexEntry);
    } catch {
      return [];
    }
  }

  private writeIndexEntry(nextEntry: CacheIndexEntry): void {
    const deduped = this.readIndex().filter((entry) => entry.key !== nextEntry.key);
    this.writeIndex([nextEntry, ...deduped]);
  }

  private writeIndex(entries: CacheIndexEntry[]): void {
    if (!this.storage) return;

    try {
      this.storage.setItem(INDEX_STORAGE_KEY, JSON.stringify(entries));
    } catch {
      this.storage.removeItem(INDEX_STORAGE_KEY);
    }
  }
}

export function createResponseCacheAdapter(
  networkAdapter: AxiosAdapter,
  options: ApiResponseCacheOptions = {},
): AxiosAdapter {
  const cache = new ApiResponseCache(options);

  return async (config) => {
    const cachedResponse = cache.get(config);
    if (cachedResponse) return cachedResponse;

    const response = await networkAdapter(config);
    if (cache.isMutation(config) && isSuccessfulResponse(response)) {
      cache.clear();
      return response;
    }

    cache.set(config, response);
    return response;
  };
}

function isSuccessfulResponse(response: AxiosResponse): boolean {
  return response.status >= 200 && response.status < 300;
}

function responseCacheOptions(
  config: InternalAxiosRequestConfig,
): ResponseCacheRequestOptions | undefined {
  return (config as ResponseCacheConfig).responseCache;
}

function isCacheableResponse(response: AxiosResponse): boolean {
  if (!isSuccessfulResponse(response)) return false;

  const contentType = readHeader(response.headers, "content-type");
  if (contentType && !contentType.toLowerCase().includes("json")) {
    return typeof response.data === "string";
  }
  return true;
}

function recordToResponse(
  record: CachedResponseRecord,
  config: InternalAxiosRequestConfig,
): AxiosResponse {
  return {
    data: record.data,
    status: record.status,
    statusText: record.statusText,
    headers: record.headers,
    config,
    request: { responseCache: "hit" },
  };
}

function buildRequestCacheKey(config: InternalAxiosRequestConfig): string {
  return [
    (config.method ?? "get").toLowerCase(),
    String(config.baseURL ?? ""),
    String(config.url ?? ""),
    stableStringify(normalizeSerializable(config.params)),
  ].join(" ");
}

function headersToRecord(headers: AxiosResponse["headers"]): RawAxiosResponseHeaders {
  const toJson = (headers as { toJSON?: () => unknown }).toJSON;
  const source = typeof toJson === "function" ? toJson.call(headers) : headers;
  if (!source || typeof source !== "object") return {};

  return Object.fromEntries(
    Object.entries(source as Record<string, unknown>).map(([key, value]) => [
      key,
      String(value),
    ]),
  );
}

function requestHeaderIncludes(
  config: InternalAxiosRequestConfig,
  headerName: string,
  expectedValue: string,
): boolean {
  const value = readHeader(config.headers, headerName);
  return value.toLowerCase().includes(expectedValue.toLowerCase());
}

function readHeader(headers: unknown, headerName: string): string {
  if (!headers || typeof headers !== "object") return "";

  const getHeader = (headers as { get?: (name: string) => unknown }).get;
  if (typeof getHeader === "function") {
    const value = getHeader.call(headers, headerName);
    return value === undefined || value === null ? "" : String(value);
  }

  const target = headerName.toLowerCase();
  for (const [key, value] of Object.entries(headers as Record<string, unknown>)) {
    if (key.toLowerCase() === target) {
      return value === undefined || value === null ? "" : String(value);
    }
  }
  return "";
}

function normalizePath(url: string): string {
  try {
    return new URL(url, "http://cache.local").pathname;
  } catch {
    return url.split("?")[0] ?? url;
  }
}

function storageKeyFor(key: string): string {
  return `${ENTRY_STORAGE_PREFIX}:${hashString(key)}`;
}

function hashString(value: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(36);
}

function normalizeSerializable(value: unknown): unknown {
  if (value === undefined) return null;
  if (value === null) return null;
  if (typeof value !== "object") return value;
  if (value instanceof Date) return value.toISOString();
  if (value instanceof URLSearchParams) return [...value.entries()];
  if (Array.isArray(value)) return value.map(normalizeSerializable);

  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, entryValue]) => entryValue !== undefined)
    .sort(([left], [right]) => left.localeCompare(right));

  return Object.fromEntries(
    entries.map(([key, entryValue]) => [key, normalizeSerializable(entryValue)]),
  );
}

function stableStringify(value: unknown): string {
  return JSON.stringify(value);
}

function safeJsonStringify(value: unknown): string | null {
  try {
    return JSON.stringify(value);
  } catch {
    return null;
  }
}

function getBrowserStorage(): Storage | null {
  if (typeof window === "undefined") return null;

  try {
    const storage = window.localStorage;
    const probeKey = `${CACHE_PREFIX}:probe`;
    storage.setItem(probeKey, "1");
    storage.removeItem(probeKey);
    return storage;
  } catch {
    return null;
  }
}

function isRecordForKey(
  value: Partial<CachedResponseRecord>,
  key: string,
): value is CachedResponseRecord {
  return (
    value.version === CACHE_VERSION &&
    value.key === key &&
    typeof value.storedAt === "number" &&
    typeof value.expiresAt === "number" &&
    typeof value.status === "number" &&
    typeof value.statusText === "string" &&
    value.headers !== undefined &&
    "data" in value
  );
}

function isCacheIndexEntry(value: unknown): value is CacheIndexEntry {
  if (!value || typeof value !== "object") return false;
  const entry = value as Partial<CacheIndexEntry>;
  return (
    typeof entry.key === "string" &&
    typeof entry.storageKey === "string" &&
    typeof entry.storedAt === "number"
  );
}
