"use client";

import { useToastStore, type ToastLevel } from "@/stores/toastStore";
import { cn } from "@/lib/utils/cn";

const levelStyles: Record<ToastLevel, string> = {
  info: "border-blue-200 bg-blue-50 text-blue-900",
  success: "border-green-200 bg-green-50 text-green-900",
  warning: "border-yellow-200 bg-yellow-50 text-yellow-900",
  error: "border-red-200 bg-red-50 text-red-900",
};

const levelIcon: Record<ToastLevel, string> = {
  info: "ℹ",
  success: "✓",
  warning: "⚠",
  error: "✕",
};

export function NotificationToast() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "flex min-w-[300px] max-w-[420px] items-start gap-3 rounded-lg border p-4 shadow-lg",
            "animate-in slide-in-from-right",
            levelStyles[toast.level],
          )}
        >
          <span className="mt-0.5 text-lg leading-none">
            {levelIcon[toast.level]}
          </span>
          <div className="flex-1">
            <p className="text-sm font-medium">{toast.title}</p>
            {toast.message && (
              <p className="mt-1 text-sm opacity-80">{toast.message}</p>
            )}
          </div>
          <button
            onClick={() => removeToast(toast.id)}
            className="cursor-pointer text-lg leading-none opacity-60 hover:opacity-100"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
