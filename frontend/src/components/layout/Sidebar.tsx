"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, MessageSquare } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { cn } from "@/lib/utils/cn";
import type { ComponentType } from "react";

interface NavItem {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { label: "AI Chat", href: "/chat", icon: MessageSquare },
  { label: "Evidence", href: "/evidence", icon: Search },
];

interface SidebarProps {
  /** When true, renders as a mobile overlay instead of inline. */
  mobile?: boolean;
  /** Callback when a nav link is clicked (used to close mobile overlay). */
  onNavigate?: () => void;
}

export function Sidebar({ mobile, onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const effectiveCollapsed = mobile ? false : collapsed;

  return (
    <aside
      aria-label="Main navigation"
      className={cn(
        "flex h-full flex-col border-r border-gray-200 bg-white transition-[width] duration-200",
        mobile ? "w-60" : effectiveCollapsed ? "w-16" : "w-60",
      )}
    >
      {/* Brand */}
      <div className="flex h-14 items-center border-b border-gray-200 px-4">
        {effectiveCollapsed ? (
          <span
            className="text-lg font-bold text-primary-700"
            aria-hidden="true"
          >
            A
          </span>
        ) : (
          <span className="text-lg font-bold text-primary-700">
            Cross Evidence
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-4" aria-label="Main">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-label={effectiveCollapsed ? item.label : undefined}
              aria-current={isActive ? "page" : undefined}
              onClick={onNavigate}
              className={cn(
                "flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium",
                "transition-colors duration-150",
                "cursor-pointer",
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!effectiveCollapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-200 p-4">
        {!effectiveCollapsed && (
          <p className="text-xs text-gray-400">Cross Evidencev0.1.0</p>
        )}
      </div>
    </aside>
  );
}
