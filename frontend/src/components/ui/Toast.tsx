"use client";

import { Info, CheckCircle, AlertTriangle, XCircle, X } from "lucide-react";
import { useToastStore, type ToastLevel } from "@/stores/toastStore";
import { cn } from "@/lib/utils/cn";
import type { ComponentType } from "react";

const levelStyles: Record<ToastLevel, string> = {
  info: "border-blue-200 bg-blue-50 text-blue-900",
  success: "border-green-200 bg-green-50 text-green-900",
  warning: "border-yellow-200 bg-yellow-50 text-yellow-900",
  error: "border-red-200 bg-red-50 text-red-900",
};

const levelIcon: Record<ToastLevel, ComponentType<{ className?: string }>> = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: XCircle,
};

export function NotificationToast() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-label="Notifications"
      className="fixed bottom-4 right-4 z-[100] flex w-[calc(100-2rem)] max-w-sm flex-col gap-2 sm:max-w-md"
    >
      {toasts.map((toast) => {
        const Icon = levelIcon[toast.level];
        return (
          <div
            key={toast.id}
            role="alert"
            className={cn(
              "flex items-start gap-3 rounded-lg border p-4 shadow-lg",
              "animate-in slide-in-from-right",
              levelStyles[toast.level],
            )}
          >
            <Icon className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{toast.title}</p>
              {toast.message && (
                <p className="mt-1 text-sm opacity-80">{toast.message}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded opacity-60 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
              aria-label="Dismiss notification"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
