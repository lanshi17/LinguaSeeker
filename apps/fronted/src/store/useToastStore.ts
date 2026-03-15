import { create } from 'zustand';

import type { ToastLevel } from '../components/feedback/notification-toast';

export type Toast = {
  id: string;
  level: ToastLevel;
  title: string;
  message?: string;
  createdAt?: number;
  ttlMs?: number;
};

type ToastState = {
  toasts: Toast[];
  pushToast: (toast: Omit<Toast, 'id' | 'createdAt'> & { id?: string; createdAt?: number }) => string;
  removeToast: (id: string) => void;
  clearToasts: () => void;
};

function randomId(prefix: string) {
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  pushToast: (toast) => {
    const id = toast.id ?? randomId('toast');
    const createdAt = toast.createdAt ?? Date.now();

    set((s) => ({
      toasts: [...s.toasts, { ...toast, id, createdAt }]
    }));

    return id;
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clearToasts: () => set({ toasts: [] })
}));
