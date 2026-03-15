import { createBrowserRouter, Navigate } from 'react-router-dom';

import { AppShell } from '../components/layout/app-shell';
import { DocumentPage } from '../pages/documents/document-page';
import { LoginPage } from '../pages/login/login-page';
import { RegisterPage } from '../pages/login/register-page';
import { RequestExportPage } from '../pages/requests/request-export-page';
import { RequestMonitorPage } from '../pages/requests/request-monitor-page';
import { PubmedCandidatesPage } from '../pages/tasks/pubmed-candidates-page';
import { TaskNewPage } from '../pages/tasks/task-new-page';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/tasks/new" replace /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'tasks/new', element: <TaskNewPage /> },
      { path: 'tasks/pubmed/candidates', element: <PubmedCandidatesPage /> },
      { path: 'requests/:requestId', element: <RequestMonitorPage /> },
      { path: 'requests/:requestId/export', element: <RequestExportPage /> },
      { path: 'documents/:documentId', element: <DocumentPage /> },
      { path: '*', element: <div style={{ padding: 24 }}>404</div> }
    ]
  }
]);
