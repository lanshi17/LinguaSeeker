import { useLocation, useNavigate } from "react-router-dom";
import { MessageSquare, Database, ClipboardList, ShieldCheck, type LucideIcon } from "lucide-react";
import { Menu, Typography } from "antd";
import { useAppStore } from "@/stores/appStore";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { label: "AI Chat", href: "/chat", icon: MessageSquare },
  { label: "Tasks", href: "/pipeline", icon: ClipboardList },
  { label: "Evidence DB", href: "/evidence-db", icon: Database },
  { label: "Audit", href: "/audit", icon: ShieldCheck },
];

interface SidebarProps {
  /** When true, renders as a mobile overlay instead of inline. */
  mobile?: boolean;
  /** Callback when a nav link is clicked (used to close mobile overlay). */
  onNavigate?: () => void;
}

export function Sidebar({ mobile, onNavigate }: SidebarProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const effectiveCollapsed = mobile ? false : collapsed;

  const selectedKey =
    NAV_ITEMS.find(
      (item) => pathname === item.href || pathname.startsWith(item.href + "/"),
    )?.href ?? "";

  const sidebarWidth = mobile ? 240 : effectiveCollapsed ? 80 : 240;

  return (
    <aside
      aria-label="Main navigation"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        width: sidebarWidth,
        borderRight: "1px solid #e5e7eb",
        backgroundColor: "#fff",
        transition: "width 200ms",
      }}
    >
      {/* Brand */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          height: 56,
          borderBottom: "1px solid #e5e7eb",
          padding: "0 16px",
        }}
      >
        <Typography.Text
          strong
          style={{ fontSize: 18, color: "var(--color-primary-700)" }}
          aria-hidden={effectiveCollapsed}
        >
          {effectiveCollapsed ? "A" : "Lingua Seeker"}
        </Typography.Text>
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
            return {
              key: item.href,
              icon: <Icon size={20} />,
              label: item.label,
            };
          })}
          style={{ border: "none" }}
        />
      </div>

      {/* Footer */}
      <div style={{ borderTop: "1px solid #e5e7eb", padding: 16 }}>
        {!effectiveCollapsed && (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Lingua Seeker v0.1.0
          </Typography.Text>
        )}
      </div>
    </aside>
  );
}
