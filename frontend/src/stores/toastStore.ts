/**
 * Global toast notification store.
 *
 * Any component can push a toast via `useToastStore.getState().addToast()`.
 * The root layout renders <NotificationToast /> which subscribes to this store.
 */

import { create } from "zustand";

export type ToastLevel = "info" | "success" | "warning" | "error";

export interface Toast {
  id: string;
  level: ToastLevel;
  title: string;
  message?: string;
  /** Auto-dismiss after this many milliseconds. Default 4000. */
  ttl?: number;
}

interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

let nextId = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (toast) => {
    const id = `toast-${++nextId}`;
    const ttl = toast.ttl ?? 4000;

    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));

    if (ttl > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, ttl);
    }
  },

  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));
