/**
 * Router Configuration
 * RESTful API style routes with /api/v1/ prefix
 */
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Layout } from '../components/Layout/Layout';
import { HomePage } from '../pages/HomePage/HomePage';
import { AnalysisPage } from '../pages/AnalysisPage/AnalysisPage';
import { GraphPage } from '../pages/GraphPage/GraphPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'analysis/:id',
        element: <AnalysisPage />,
      },
      {
        path: 'graph',
        element: <GraphPage />,
      },
      // API 风格路由重定向
      {
        path: 'api/v1/documents/:id',
        element: <Navigate to="/analysis/:id" replace />,
      },
      {
        path: 'api/v1/graph',
        element: <Navigate to="/graph" replace />,
      },
    ],
  },
]);
