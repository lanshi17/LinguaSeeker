import { createBrowserRouter, Navigate } from 'react-router-dom';

import { AppShell } from '../components/layout/app-shell';
import { DocumentPage } from '../pages/documents/document-page';
import { LoginPage } from '../pages/login/login-page';
import { RegisterPage } from '../pages/login/register-page';
import { GraphPage } from '../pages/graph/graph-page';
import { NotFoundPage } from '../pages/not-found/not-found-page';
import { RequestExportPage } from '../pages/requests/request-export-page';
import { RequestMonitorPage } from '../pages/requests/request-monitor-page';
import { LiteratureCandidatesPage } from '../pages/tasks/literature-candidates-page';
import { AgentTaskCreatePage } from '../pages/tasks/agent-task-create-page';
import { TaskNewPage } from '../pages/tasks/task-new-page';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/tasks/agent-create" replace /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'tasks/agent-create', element: <AgentTaskCreatePage /> },
      { path: 'tasks/new', element: <TaskNewPage /> },
      { path: 'graph', element: <GraphPage /> },
      { path: 'tasks/literature/candidates', element: <LiteratureCandidatesPage /> },
      { path: 'requests/:requestId', element: <RequestMonitorPage /> },
      { path: 'requests/:requestId/export', element: <RequestExportPage /> },
      { path: 'documents/:documentId', element: <DocumentPage /> },
      { path: '*', element: <NotFoundPage /> }
    ]
  }
]);
