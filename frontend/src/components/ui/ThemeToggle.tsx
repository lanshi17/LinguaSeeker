import { Button, Tooltip } from "antd";
import { Sun, Moon } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useI18n } from "@/lib/i18n";

/** Compact theme toggle button — sun/moon icon, switches light ↔ dark. */
export function ThemeToggle() {
  const mode = useAppStore((s) => s.mode);
  const setMode = useAppStore((s) => s.setMode);
  const { t } = useI18n();

  const isDark = mode === "dark";
  const tooltip = isDark ? t("theme.light") : t("theme.dark");

  return (
    <Tooltip title={tooltip}>
      <Button
        type="text"
        size="small"
        icon={isDark ? <Sun size={15} /> : <Moon size={15} />}
        onClick={() => {
          document.documentElement.classList.add("theme-transitioning");
          setMode(isDark ? "light" : "dark");
          setTimeout(() => document.documentElement.classList.remove("theme-transitioning"), 350);
        }}
        style={{
          display: "flex",
          alignItems: "center",
          color: "var(--color-text-secondary)",
          padding: 0,
          width: 28,
          height: 28,
        }}
      />
    </Tooltip>
  );
}
