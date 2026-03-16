import React from 'react';
import ReactDOM from 'react-dom/client';

import 'antd/dist/reset.css';

import App from './App';
import './assets/globals.css';
import { initGlobalErrorHandler } from './utils/globalErrorHandler';

initGlobalErrorHandler();

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error('Root element #root not found');
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
