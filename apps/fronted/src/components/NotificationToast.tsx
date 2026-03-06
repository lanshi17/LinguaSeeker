import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { useAppStore } from '../stores';
import type { Notification } from '../stores/notificationStore';
import './NotificationToast.css';

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const Toast: React.FC<{
  notification: Notification;
  onClose: () => void;
}> = ({ notification, onClose }) => {
  const Icon = iconMap[notification.type];
  
  useEffect(() => {
    if (notification.autoDismiss) {
      const timer = setTimeout(onClose, notification.dismissAfter);
      return () => clearTimeout(timer);
    }
  }, [notification.autoDismiss, notification.dismissAfter, onClose]);
  
  return (
    <div className={`notification-toast notification-${notification.type}`}>
      <Icon className="notification-icon" size={20} />
      <span className="notification-message">{notification.message}</span>
      <button 
        className="notification-close" 
        onClick={onClose}
        aria-label="Close notification"
      >
        <X size={16} />
      </button>
    </div>
  );
};

export const NotificationToast: React.FC = () => {
  const notifications = useAppStore(s => s.notifications);
  const removeNotification = useAppStore(s => s.removeNotification);
  
  if (notifications.length === 0) return null;
  
  return (
    <div className="notification-container">
      {notifications.map(notification => (
        <Toast
          key={notification.id}
          notification={notification}
          onClose={() => removeNotification(notification.id)}
        />
      ))}
    </div>
  );
};