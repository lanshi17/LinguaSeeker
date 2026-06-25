import { useState, useCallback } from "react";
import { Layout, Button } from "antd";
import { Menu, X, List } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { ConnectionStatus } from "./ConnectionStatus";
import { AnimatedOutlet } from "@/components/ui/PageTransition";
import { useAppStore } from "@/stores/appStore";

const { Content } = Layout;

export function DashboardLayout() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const closeMobileMenu = useCallback(() => setMobileMenuOpen(false), []);

  return (
      <div className="dl-root" style={{ display: "flex", height: "100vh", overflow: "hidden", backgroundColor: "#f9fafb" }}>
        {/* Desktop sidebar */}
        <div className="dl-desktop-sidebar">
          <Sidebar />
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
            aria-label="Navigation menu"
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
              borderBottom: "1px solid #e5e7eb",
              backgroundColor: "#fff",
            }}
          >
            {/* Mobile hamburger */}
            <Button
              type="text"
              icon={mobileMenuOpen ? <X style={{ width: 18, height: 18 }} /> : <Menu style={{ width: 18, height: 18 }} />}
              onClick={() => setMobileMenuOpen((o) => !o)}
              aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
              className="dl-mobile-btn"
              style={{
                alignItems: "center",
                justifyContent: "center",
                color: "#6b7280",
              }}
            />

            {/* Desktop collapse toggle */}
            <Button
              type="text"
              icon={<List style={{ width: 18, height: 18 }} />}
              onClick={toggleSidebar}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="dl-desktop-btn"
              style={{
                alignItems: "center",
                justifyContent: "center",
                color: "#6b7280",
              }}
            />

            <ConnectionStatus />
          </header>

          {/* Main content */}
          <Content className="dl-main" style={{ flex: 1, overflowY: "auto" }}>
            <div style={{ maxWidth: 1280, margin: "0 auto" }}>
              <AnimatedOutlet />
            </div>
          </Content>
        </div>
      </div>
  );
}
