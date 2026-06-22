import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ChatPage } from "@/pages/ChatPage";
import { ChatSessionPage } from "@/pages/ChatSessionPage";

const EvidencePage = lazy(() => import("@/pages/EvidencePage").then(m => ({ default: m.EvidencePage })));
const EvidenceDetailPage = lazy(() => import("@/pages/EvidenceDetailPage").then(m => ({ default: m.EvidenceDetailPage })));
const EvidenceDbPage = lazy(() => import("@/pages/EvidenceDbPage").then(m => ({ default: m.EvidenceDbPage })));
const PipelinePage = lazy(() => import("@/pages/PipelinePage").then(m => ({ default: m.PipelinePage })));
const PipelineRunPage = lazy(() => import("@/pages/PipelineRunPage").then(m => ({ default: m.PipelineRunPage })));

export function App() {
  return (
    <Suspense>
      <Routes>
        <Route index element={<Navigate to="/chat" replace />} />
        <Route element={<DashboardLayout />}>
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:sessionId" element={<ChatSessionPage />} />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route path="/evidence/detail" element={<EvidenceDetailPage />} />
          <Route path="/evidence-db" element={<EvidenceDbPage />} />
          <Route path="/evidence-db/:variantSlug" element={<EvidenceDbPage />} />
          <Route path="/evidence-db/:variantSlug/:sourceDocId" element={<EvidenceDbPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/pipeline/:runId" element={<PipelineRunPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </Suspense>
  );
}
