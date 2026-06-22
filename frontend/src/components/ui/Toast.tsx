import { useState } from "react";
import { Info, CheckCircle, AlertTriangle, XCircle, X } from "lucide-react";
import { useToastStore, type ToastLevel } from "@/stores/toastStore";
import type { ComponentType, CSSProperties } from "react";

interface LevelStyle {
  borderColor: string;
  backgroundColor: string;
  color: string;
}

const levelStyles: Record<ToastLevel, LevelStyle> = {
  info: { borderColor: "#bfdbfe", backgroundColor: "#eff6ff", color: "#1e3a8a" },
  success: { borderColor: "#bbf7d0", backgroundColor: "#f0fdf4", color: "#14532d" },
  warning: { borderColor: "#fde68a", backgroundColor: "#fffbeb", color: "#713f12" },
  error: { borderColor: "#fecaca", backgroundColor: "#fef2f2", color: "#7f1d1d" },
};

const levelIcon: Record<ToastLevel, ComponentType<{ style?: CSSProperties }>> = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: XCircle,
};

const iconStyle: CSSProperties = {
  marginTop: 2,
  width: 20,
  height: 20,
  flexShrink: 0,
};

function DismissButton({ onClick }: { onClick: () => void }) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      aria-label="Dismiss notification"
      style={{
        display: "flex",
        height: 24,
        width: 24,
        flexShrink: 0,
        cursor: "pointer",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 4,
        border: "none",
        background: "transparent",
        color: "inherit",
        opacity: hovered ? 1 : 0.6,
        transition: "opacity 150ms",
        outline: focused ? "2px solid currentColor" : "none",
        outlineOffset: 1,
      }}
    >
      <X style={{ width: 16, height: 16 }} />
    </button>
  );
}

export function NotificationToast() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <>
      <style>{`
        .toast-container { max-width: 384px; }
        @media (min-width: 640px) {
          .toast-container { max-width: 448px; }
        }
      `}</style>
      <div
        aria-live="polite"
        aria-label="Notifications"
        className="toast-container"
        style={{
          position: "fixed",
          bottom: 16,
          right: 16,
          zIndex: 100,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          width: "calc(100vw - 2rem)",
        }}
      >
        {toasts.map((toast) => {
          const Icon = levelIcon[toast.level];
          return (
            <div
              key={toast.id}
              role="alert"
              className="animate-in slide-in-from-right"
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 12,
                borderRadius: 8,
                border: `1px solid ${levelStyles[toast.level].borderColor}`,
                backgroundColor: levelStyles[toast.level].backgroundColor,
                color: levelStyles[toast.level].color,
                padding: 16,
                boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
              }}
            >
              <Icon style={iconStyle} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <p style={{ fontSize: 14, fontWeight: 500, margin: 0 }}>{toast.title}</p>
                {toast.message && (
                  <p style={{ fontSize: 14, margin: "4px 0 0", opacity: 0.8 }}>{toast.message}</p>
                )}
              </div>
              <DismissButton onClick={() => removeToast(toast.id)} />
            </div>
          );
        })}
      </div>
    </>
  );
}
