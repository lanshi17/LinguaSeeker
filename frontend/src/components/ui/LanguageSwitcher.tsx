import { Button, Tooltip } from "antd";
import { Globe } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useI18n } from "@/lib/i18n";

/**
 * Compact language toggle button.
 * Renders "EN"/"中" label with a globe icon.
 */
export function LanguageSwitcher() {
  const locale = useAppStore((s) => s.locale);
  const setLocale = useAppStore((s) => s.setLocale);
  const { t } = useI18n();

  const nextLabel = locale === "zh" ? "EN" : "中";
  const tooltip = locale === "zh" ? t("lang.switchToEn") : t("lang.switchToZh");

  return (
    <Tooltip title={tooltip}>
      <Button
        type="text"
        size="small"
        icon={<Globe size={15} />}
        onClick={() => setLocale(locale === "zh" ? "en" : "zh")}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontSize: 12,
          color: "var(--color-text-secondary)",
          padding: "0 8px",
          height: 28,
        }}
      >
        {nextLabel}
      </Button>
    </Tooltip>
  );
}
