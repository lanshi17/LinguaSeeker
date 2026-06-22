import { useState, useCallback } from "react";
import { Menu, X } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { ConnectionStatus } from "./ConnectionStatus";
import { AnimatedOutlet } from "@/components/ui/PageTransition";
import { useAppStore } from "@/stores/appStore";
import { cn } from "@/lib/utils/cn";

export function DashboardLayout() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const closeMobileMenu = useCallback(() => setMobileMenuOpen(false), []);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Desktop sidebar */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          <div
            className="fixed inset-0 bg-black/30"
            onClick={closeMobileMenu}
            aria-hidden="true"
          />
          <div className="fixed inset-y-0 left-0 z-50 w-60">
            <Sidebar mobile onNavigate={closeMobileMenu} />
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 md:px-6">
          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileMenuOpen((o) => !o)}
            aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            className="cursor-pointer rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 md:hidden"
          >
            {mobileMenuOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>

          {/* Desktop collapse toggle */}
          <button
            onClick={toggleSidebar}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden cursor-pointer rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 md:block"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h6a1 1 0 110 2H4a1 1 0 01-1-1z"
                clipRule="evenodd"
              />
            </svg>
          </button>

          <ConnectionStatus />
        </header>

        {/* Main content */}
        <main
          className={cn(
            "flex-1 overflow-y-auto p-4 md:p-6",
            "transition-[padding] duration-200",
          )}
        >
          <div className="mx-auto max-w-7xl"><AnimatedOutlet /></div>
        </main>
      </div>
    </div>
  );
}
