"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppStore } from "@/stores/appStore";
import { cn } from "@/lib/utils/cn";

interface NavItem {
  label: string;
  href: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Pipeline", href: "/pipeline", icon: "⟶" },
  { label: "Tasks", href: "/tasks/agent-create", icon: "✦" },
  { label: "Evidence", href: "/evidence/audit", icon: "◈" },
  { label: "Chat", href: "/chat", icon: "◉" },
  { label: "Graph", href: "/graph", icon: "◇" },
  { label: "Settings", href: "/settings", icon: "⚙" },
];

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useAppStore((s) => s.sidebarCollapsed);

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-gray-200 bg-white transition-[width] duration-200",
        collapsed ? "w-16" : "w-60",
      )}
    >
      {/* Brand */}
      <div className="flex h-14 items-center border-b border-gray-200 px-4">
        <span
          className={cn(
            "text-lg font-bold text-primary-700 transition-opacity",
            collapsed && "opacity-0",
          )}
        >
          ACMG Lingua
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-4">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium",
                "transition-colors duration-150",
                "cursor-pointer",
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
              )}
            >
              <span className="text-base">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-200 p-4">
        {!collapsed && (
          <p className="text-xs text-gray-400">ACMG Lingua v0.1.0</p>
        )}
      </div>
    </aside>
  );
}
