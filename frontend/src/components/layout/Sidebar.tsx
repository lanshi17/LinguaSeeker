import { useI18n } from "@/lib/i18n";
import { useAppStore } from "@/stores/appStore";
import { Menu, Typography } from "antd";
import {
  ClipboardList,
  Database,
  HelpCircle,
  MessageSquare,
  Network,
  ShieldCheck,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

interface SidebarProps {
  /** When true, renders as a mobile overlay instead of inline. */
  mobile?: boolean;
  /** Callback when a nav link is clicked (used to close mobile overlay). */
  onNavigate?: () => void;
  /** Callback to open the user guide. */
  onGuideOpen?: () => void;
}

export function Sidebar({ mobile, onNavigate, onGuideOpen }: SidebarProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const mode = useAppStore((s) => s.mode);
  const effectiveCollapsed = mobile ? false : collapsed;
  const { t } = useI18n();

  // The SVG is always the bright (light) version. In dark mode we invert it
  // so the white background becomes dark and the colours stay reasonable.
  const logoFilter =
    mode === "dark" ? "invert(1) hue-rotate(180deg)" : undefined;

  const NAV_ITEMS = [
    { label: t("nav.evidenceDb"), href: "/evidence-db", icon: Database },
    { label: t("nav.chat"), href: "/chat", icon: MessageSquare },
    { label: t("nav.graphRag"), href: "/graphrag", icon: Network },
    { label: t("nav.tasks"), href: "/pipeline", icon: ClipboardList },
    { label: t("nav.audit"), href: "/audit", icon: ShieldCheck },
  ] as const;

  const selectedKey =
    NAV_ITEMS.find(
      (item) => pathname === item.href || pathname.startsWith(item.href + "/"),
    )?.href ?? "";

  const sidebarWidth = mobile ? 240 : effectiveCollapsed ? 80 : 240;

  return (
    <aside
      aria-label={t("aria.mainNav")}
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        width: sidebarWidth,
        borderRight: "1px solid var(--color-border)",
        backgroundColor: "var(--color-surface)",
        transition: "width 200ms",
      }}
    >
      {/* Brand */}
      <div
        data-tour="brand"
        style={{
          display: "flex",
          alignItems: "center",
          height: 56,
          borderBottom: "1px solid var(--color-border)",
          padding: "0 16px",
        }}
      >
        <img
          src="https://acmg-bucket.oss-cn-shenzhen.aliyuncs.com/favicon.svg"
          alt="Lingua Seeker logo"
          width={28}
          height={28}
          style={{ borderRadius: 4, flexShrink: 0, filter: logoFilter }}
        />
        {!effectiveCollapsed && (
          <Typography.Text
            style={{
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--color-text)",
              marginLeft: 10,
            }}
          >
            Lingua Seeker
          </Typography.Text>
        )}
      </div>

      {/* Navigation */}
      <div style={{ flex: 1, padding: "16px 0" }}>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          inlineCollapsed={!mobile && effectiveCollapsed}
          onClick={({ key }) => {
            navigate(key);
            onNavigate?.();
          }}
          items={NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const tourKey = item.href.replace("/", "nav-");
            return {
              key: item.href,
              icon: <Icon size={20} />,
              label: <span data-tour={tourKey}>{item.label}</span>,
            };
          })}
          style={{ border: "none" }}
        />
      </div>

      {/* Footer */}
      <div
        style={{
          borderTop: "1px solid var(--color-border)",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        {!effectiveCollapsed && (
          <>
            <button
              data-tour="help-btn"
              onClick={onGuideOpen}
              aria-label={t("nav.help")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                padding: "6px 0",
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "var(--color-text-secondary)",
                fontSize: 13,
                fontFamily: "inherit",
                transition: "color 150ms",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.color = "var(--color-primary-600)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.color = "var(--color-text-secondary)")
              }
            >
              <HelpCircle size={16} />
              <span>{t("nav.help")}</span>
            </button>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Lingua Seeker v{__APP_VERSION__}
            </Typography.Text>
          </>
        )}
      </div>
    </aside>
  );
}
