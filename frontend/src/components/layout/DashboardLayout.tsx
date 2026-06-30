import { useState, useCallback, useEffect } from "react";
import { Layout, Button } from "antd";
import { Menu, X, List } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { AnimatedOutlet } from "@/components/ui/PageTransition";
import { useAppStore } from "@/stores/appStore";
import { UserGuide, hasSeenGuide } from "@/components/ui/UserGuide";
import { useI18n } from "@/lib/i18n";
import { LanguageSwitcher } from "@/components/ui/LanguageSwitcher";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
const { Content } = Layout;

export function DashboardLayout() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { t } = useI18n();
  const closeMobileMenu = useCallback(() => setMobileMenuOpen(false), []);
  const [guideOpen, setGuideOpen] = useState(false);

  // Auto-show guide for first-time visitors
  useEffect(() => {
    if (!hasSeenGuide()) {
      // Small delay so the page finishes rendering before Tour targets exist
      const timer = setTimeout(() => setGuideOpen(true), 600);
      return () => clearTimeout(timer);
    }
  }, []);

  return (
      <div className="dl-root" style={{ display: "flex", height: "100vh", overflow: "hidden", backgroundColor: "var(--color-bg)" }}>
        {/* Desktop sidebar */}
        <div className="dl-desktop-sidebar">
          <Sidebar onGuideOpen={() => setGuideOpen(true)} />
        </div>

        {/* Mobile sidebar overlay */}
        {mobileMenuOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 40,
            }}
            role="dialog"
            aria-modal="true"
            aria-label={t("layout.openMenu")}
          >
            <div
              style={{
                position: "fixed",
                inset: 0,
                backgroundColor: "rgba(0, 0, 0, 0.3)",
              }}
              onClick={closeMobileMenu}
              aria-hidden="true"
            />
            <div
              style={{
                position: "fixed",
                top: 0,
                bottom: 0,
                left: 0,
                zIndex: 50,
                width: 240,
              }}
            >
              <Sidebar mobile onNavigate={closeMobileMenu} />
            </div>
          </div>
        )}

        <div className="dl-body" style={{ display: "flex", flex: 1, flexDirection: "column", overflow: "hidden" }}>
          {/* Top bar */}
          <header
            className="dl-header"
            style={{
              display: "flex",
              height: 56,
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: "1px solid var(--color-border)",
              backgroundColor: "var(--color-header-bg)",
            }}
          >
            {/* Mobile hamburger */}
            <Button
              type="text"
              icon={mobileMenuOpen ? <X style={{ width: 18, height: 18 }} /> : <Menu style={{ width: 18, height: 18 }} />}
              onClick={() => setMobileMenuOpen((o) => !o)}
              aria-label={mobileMenuOpen ? t("layout.closeMenu") : t("layout.openMenu")}
              className="dl-mobile-btn"
              style={{
                alignItems: "center",
                justifyContent: "center",
                color: "var(--color-text-secondary)",
              }}
            />

            {/* Desktop collapse toggle */}
            <Button
              type="text"
              icon={<List style={{ width: 18, height: 18 }} />}
              onClick={toggleSidebar}
              aria-label={collapsed ? t("layout.expandSidebar") : t("layout.collapseSidebar")}
              className="dl-desktop-btn"
              style={{
                alignItems: "center",
                justifyContent: "center",
                color: "var(--color-text-secondary)",
              }}
            />

            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <ThemeToggle />
              <LanguageSwitcher />
            </div>
          </header>

          {/* Main content */}
          <Content className="dl-main" style={{ flex: 1, overflowY: "auto" }}>
            <div style={{ maxWidth: 1280, margin: "0 auto" }}>
              <AnimatedOutlet />
            </div>
          </Content>
        </div>
        <UserGuide open={guideOpen} onClose={() => setGuideOpen(false)} />
      </div>
  );
}
