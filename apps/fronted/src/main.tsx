import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import AppRoutes from './App';
import { initGlobalErrorHandler } from './utils/errorHandler';
import { NotificationToast } from './components/NotificationToast';
import './assets/globals.css';

initGlobalErrorHandler();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <NotificationToast />
      <AppRoutes />
    </BrowserRouter>
  </React.StrictMode>,
);