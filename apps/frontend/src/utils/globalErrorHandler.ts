import { useToastStore } from '../store/useToastStore';

export function initGlobalErrorHandler() {
  const show = (title: string, message?: string) => {
    useToastStore.getState().pushToast({
      level: 'error',
      title,
      message,
      ttlMs: 8000
    });
  };

  window.addEventListener('error', (event) => {
    const msg = event.error instanceof Error ? event.error.message : event.message;
    show('Unexpected error', msg);
  });

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    const msg = reason instanceof Error ? reason.message : typeof reason === 'string' ? reason : 'Unknown rejection';
    show('Unhandled promise rejection', msg);
  });
}
