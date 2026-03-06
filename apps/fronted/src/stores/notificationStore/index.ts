import type { StateCreator } from 'zustand';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  timestamp: Date;
  autoDismiss: boolean;
  dismissAfter: number;
}

export interface NotificationSlice {
  notifications: Notification[];
  
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearAllNotifications: () => void;
  
  notifySuccess: (message: string) => void;
  notifyError: (message: string) => void;
  notifyWarning: (message: string) => void;
  notifyInfo: (message: string) => void;
}

export const createNotificationSlice: StateCreator<NotificationSlice> = (set, get) => ({
  notifications: [],
  
  addNotification: (notification) => {
    const id = `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newNotification: Notification = {
      ...notification,
      id,
      timestamp: new Date(),
    };
    
    set(state => ({
      notifications: [...state.notifications, newNotification]
    }));
    
    if (notification.autoDismiss) {
      setTimeout(() => {
        get().removeNotification(id);
      }, notification.dismissAfter || 5000);
    }
  },
  
  removeNotification: (id) => {
    set(state => ({
      notifications: state.notifications.filter(n => n.id !== id)
    }));
  },
  
  clearAllNotifications: () => {
    set({ notifications: [] });
  },
  
  notifySuccess: (message) => {
    get().addNotification({
      type: 'success',
      message,
      autoDismiss: true,
      dismissAfter: 5000,
    });
  },
  
  notifyError: (message) => {
    get().addNotification({
      type: 'error',
      message,
      autoDismiss: true,
      dismissAfter: 7000,
    });
  },
  
  notifyWarning: (message) => {
    get().addNotification({
      type: 'warning',
      message,
      autoDismiss: true,
      dismissAfter: 6000,
    });
  },
  
  notifyInfo: (message) => {
    get().addNotification({
      type: 'info',
      message,
      autoDismiss: true,
      dismissAfter: 5000,
    });
  },
});