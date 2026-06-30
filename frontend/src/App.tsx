import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { Spin } from "antd";

const ChatPage = lazy(() => import("@/pages/ChatPage").then(m => ({ default: m.ChatPage })));
const ChatSessionPage = lazy(() => import("@/pages/ChatSessionPage").then(m => ({ default: m.ChatSessionPage })));

const EvidencePage = lazy(() => import("@/pages/EvidencePage").then(m => ({ default: m.EvidencePage })));
const EvidenceDetailPage = lazy(() => import("@/pages/EvidenceDetailPage").then(m => ({ default: m.EvidenceDetailPage })));
const EvidenceDbPage = lazy(() => import("@/pages/EvidenceDbPage").then(m => ({ default: m.EvidenceDbPage })));
const PipelinePage = lazy(() => import("@/pages/PipelinePage").then(m => ({ default: m.PipelinePage })));
const PipelineRunPage = lazy(() => import("@/pages/PipelineRunPage").then(m => ({ default: m.PipelineRunPage })));
const AuditPage = lazy(() => import("@/pages/AuditPage").then(m => ({ default: m.AuditPage })));

export function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}><Spin size="large" /></div>}>
        <Routes>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route element={<DashboardLayout />}>
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:sessionId" element={<ChatSessionPage />} />
            <Route path="/evidence" element={<EvidencePage />} />
            <Route path="/evidence/detail" element={<EvidenceDetailPage />} />
            <Route path="/evidence-db" element={<EvidenceDbPage />} />
            <Route path="/evidence-db/:variantSlug" element={<EvidenceDbPage />} />
            <Route path="/evidence-db/:variantSlug/:sourceDocumentId" element={<EvidenceDbPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/pipeline/:runId" element={<PipelineRunPage />} />
            <Route path="/audit" element={<AuditPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
