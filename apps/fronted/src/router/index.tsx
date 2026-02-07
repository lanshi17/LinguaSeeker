/**
 * Router Configuration
 * RESTful API style routes with /api/v1/ prefix
 */
import { createBrowserRouter, Navigate, type LoaderFunctionArgs } from 'react-router-dom';
import { Layout } from '../components/layout/Layout/Layout';
import { HomePage } from '../pages/HomePage/HomePage';
import { AnalysisPage } from '../pages/AnalysisPage/AnalysisPage';
import { GraphPage } from '../pages/GraphPage/GraphPage';
import { TaskStatusPage } from '../pages/TaskStatusPage/TaskStatusPage';
import { DocumentViewPage } from '../pages/DocumentViewPage/DocumentViewPage';
import { EvidenceDemoPage } from '../pages/EvidenceDemoPage/EvidenceDemoPage';

/**
 * 文档加载器 - 用于分析页面
 */
const documentLoader = async ({ params }: LoaderFunctionArgs) => {
  const { id } = params;
  if (!id) {
    throw new Response('文档ID不能为空', { status: 400 });
  }
  return { documentId: id };
};

/**
 * 任务状态页面加载器
 */
const taskStatusLoader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);
  const taskId = url.searchParams.get('taskId');
  return { taskId };
};

/**
 * 路由配置
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      // ========== 主页面路由 ==========
      {
        index: true,
        element: <HomePage />,
      },
      
      // ========== 分析页面 ==========
      {
        path: 'analysis/:id',
        element: <AnalysisPage />,
        loader: documentLoader,
      },
      
      // ========== 图谱页面 ==========
      {
        path: 'graph',
        element: <GraphPage />,
      },
      
      // ========== 任务状态页面 ==========
      {
        path: 'tasks/status',
        element: <TaskStatusPage />,
        loader: taskStatusLoader,
      },
      
      // ========== 文献查看页面 ==========
      {
        path: 'documents/:documentId',
        element: <DocumentViewPage />,
        loader: documentLoader,
      },
      
      // ========== 证据可视化演示页面 ==========
      {
        path: 'evidence-demo',
        element: <EvidenceDemoPage />,
      },
      
      // ========== API 风格路由重定向 ==========
      // 任务相关路由
      {
        path: 'api/v1/tasks/:taskId/status',
        element: <Navigate to="/tasks/status?taskId=:taskId" replace />,
      },
      {
        path: 'api/v1/tasks/:taskId',
        loader: ({ params }) => {
          // 根据请求方法重定向 (实际由页面处理)
          return { taskId: params.taskId };
        },
      },
      
      // 文档相关路由
      {
        path: 'api/v1/documents/:documentId',
        element: <Navigate to="/documents/:documentId" replace />,
      },
      
      // PDF 解析路由
      {
        path: 'api/v1/pdf/upload',
        element: <Navigate to="/" replace />,
      },
      
      // 图谱搜索路由
      {
        path: 'api/v1/graph/search',
        element: <Navigate to="/graph" replace />,
      },
      {
        path: 'api/v1/graph',
        element: <Navigate to="/graph" replace />,
      },
      
      // ========== 404 页面 ==========
      {
        path: '*',
        element: (
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column',
            alignItems: 'center', 
            justifyContent: 'center',
            minHeight: '60vh',
            padding: '2rem'
          }}>
            <h1 style={{ fontSize: '4rem', marginBottom: '1rem', color: '#e5e7eb' }}>404</h1>
            <h2 style={{ marginBottom: '1rem', color: '#374151' }}>页面未找到</h2>
            <p style={{ color: '#6b7280', marginBottom: '2rem' }}>
              您访问的页面不存在或已被移除
            </p>
            <a 
              href="/" 
              style={{
                padding: '0.75rem 1.5rem',
                background: '#3b82f6',
                color: 'white',
                borderRadius: '0.5rem',
                textDecoration: 'none',
                fontWeight: 500
              }}
            >
              返回首页
            </a>
          </div>
        ),
      },
    ],
  },
]);

/**
 * 路由工具函数
 */
export const routerUtils = {
  /**
   * 获取分析页面 URL
   */
  getAnalysisUrl: (documentId: string): string => `/analysis/${encodeURIComponent(documentId)}`,
  
  /**
   * 获取任务状态页面 URL
   */
  getTaskStatusUrl: (taskId: string): string => `/tasks/status?taskId=${encodeURIComponent(taskId)}`,
  
  /**
   * 获取文献查看页面 URL
   */
  getDocumentViewUrl: (documentId: string): string => `/documents/${encodeURIComponent(documentId)}`,
  
  /**
   * 获取图谱搜索 URL
   */
  getGraphSearchUrl: (keyword?: string): string => {
    const base = '/graph';
    return keyword ? `${base}?keyword=${encodeURIComponent(keyword)}` : base;
  },
};

export default router;
