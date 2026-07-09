type DateInput = string | number | Date | null | undefined;

export const APP_TIME_ZONE = "Asia/Shanghai";

const APP_TIME_ZONE_OFFSET = "+08:00";

function parseDateInput(value: DateInput): Date | null {
  if (value == null) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

type AppTimePart = "year" | "month" | "day" | "hour" | "minute" | "second";

function getAppTimeParts(value: Date): Record<AppTimePart, string> {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: APP_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(value);
  const entries = parts
    .filter((part) => part.type !== "literal")
    .map((part) => [part.type, part.value]);
  return Object.fromEntries(entries) as Record<AppTimePart, string>;
}

export function formatDuration(totalSeconds: number | null | undefined): string {
  const s = totalSeconds ?? 0;
  if (!Number.isFinite(s) || s < 0) return "—";
  if (s < 1) return `${Math.round(s * 1000)}ms`;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  if (m < 60) return `${m}m ${r.toString().padStart(2, "0")}s`;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${h}h ${mm.toString().padStart(2, "0")}m`;
}

export function formatRelative(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const diff = Math.round((now - t) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86_400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86_400)}d ago`;
}

export function formatDate(
  value: DateInput,
  locale?: Intl.LocalesArgument,
  options: Intl.DateTimeFormatOptions = {},
): string {
  const date = parseDateInput(value);
  if (!date) return "—";
  return date.toLocaleDateString(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...options,
    timeZone: APP_TIME_ZONE,
  });
}

export function formatTime(value: DateInput, locale?: Intl.LocalesArgument): string {
  const date = parseDateInput(value);
  if (!date) return "—";
  return date.toLocaleTimeString(locale, {
    timeZone: APP_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
}

export function formatTimestamp(value: DateInput, locale?: Intl.LocalesArgument): string {
  const date = parseDateInput(value);
  if (!date) return "—";
  return date.toLocaleString(locale, {
    timeZone: APP_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
}

export function formatAppIsoTimestamp(value: DateInput = new Date()): string {
  const date = parseDateInput(value);
  if (!date) return "";
  const parts = getAppTimeParts(date);
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}${APP_TIME_ZONE_OFFSET}`;
}

export function formatFilenameTimestamp(value: DateInput = new Date()): string {
  const date = parseDateInput(value);
  if (!date) return "";
  const parts = getAppTimeParts(date);
  return `${parts.year}-${parts.month}-${parts.day}_${parts.hour}-${parts.minute}-${parts.second}`;
}
