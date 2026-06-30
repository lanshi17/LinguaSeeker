/**
 * Lightweight i18n for Lingua Seeker.
 *
 * Architecture:
 * - `translations` holds flat key → string maps per locale
 * - `useI18n()` returns a `t(key, params?)` resolver bound to the current appStore locale
 * - `LanguageSwitcher` renders a compact toggle button
 *
 * Interpolation: use `{param}` placeholders in translation values.
 * ```tsx
 * t("pipeline.success.pdfStarted", { name: "file.pdf" })
 * ```
 *
 * Adding a new locale: add a new key to `Locale`, a new map to `translations`,
 * update `detectLocale` in appStore, and add the new map to `t()`.
 */

import { useAppStore } from "@/stores/appStore";
import { en } from "./locales/en";
import { zh } from "./locales/zh";

export type Locale = "en" | "zh";

export const translations = { en, zh } as const;

/* ── Hook ──────────────────────────────────────────────────────── */

export type TFunction = (key: string, params?: Record<string, unknown>) => string;

/**
 * Returns a `t(key, params?)` function bound to the current locale from appStore.
 *
 * Supports `{param}` interpolation:
 * ```tsx
 * const { t } = useI18n();
 * <span>{t("nav.chat")}</span>
 * <span>{t("pipeline.success.pdfStarted", { name: "file.pdf" })}</span>
 * ```
 */
export function useI18n() {
  const locale = useAppStore((s) => s.locale);

  const t = (key: string, params?: Record<string, unknown>): string => {
    const template = (translations[locale] as Record<string, string>)[key]
      ?? (en as Record<string, string>)[key]
      ?? key;
    if (!params) return template;
    return Object.entries(params).reduce(
      (result, [k, v]) => result.replaceAll(`{${k}}`, String(v)),
      template,
    );
  };

  return { t, locale };
}
