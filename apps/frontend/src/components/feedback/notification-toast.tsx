import { useEffect } from 'react';

import { useToastStore } from '../../store/useToastStore';

export type ToastLevel = 'info' | 'success' | 'warning' | 'error';

const levelToColor: Record<ToastLevel, string> = {
  info: 'var(--brand)',
  success: 'var(--success)',
  warning: 'var(--warning)',
  error: 'var(--danger)'
};

export const NotificationToast: React.FC = () => {
  const { toasts, removeToast } = useToastStore();

  useEffect(() => {
    const now = Date.now();
    const timers = toasts
      .filter((t) => typeof t.ttlMs === 'number' && t.ttlMs > 0)
      .map((t) => {
        const createdAt = t.createdAt ?? now;
        const remaining = Math.max(0, createdAt + (t.ttlMs ?? 0) - Date.now());
        return window.setTimeout(() => removeToast(t.id), remaining);
      });
    return () => {
      timers.forEach((id) => window.clearTimeout(id));
    };
  }, [removeToast, toasts]);

  if (toasts.length === 0) return null;

  return (
    <div
      className="no-print"
      style={{
        position: 'fixed',
        right: 16,
        bottom: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        zIndex: 1000
      }}
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          style={{
            width: 340,
            borderRadius: 14,
            border: '1px solid var(--border)',
            background: 'rgba(10, 14, 28, 0.92)',
            boxShadow: 'var(--shadow)',
            overflow: 'hidden'
          }}
        >
          <div style={{ height: 3, background: levelToColor[t.level] }} />
          <div style={{ padding: '10px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <div style={{ fontWeight: 700 }}>{t.title}</div>
              <button
                type="button"
                onClick={() => removeToast(t.id)}
                style={{
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--text)',
                  borderRadius: 10,
                  padding: '4px 10px',
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>
            {t.message ? <div className="muted" style={{ marginTop: 6 }}>
              {t.message}
            </div> : null}
          </div>
        </div>
      ))}
    </div>
  );
};
