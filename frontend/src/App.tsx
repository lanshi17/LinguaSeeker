import { Routes, Route, Navigate } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ChatPage } from "@/pages/ChatPage";
import { ChatSessionPage } from "@/pages/ChatSessionPage";
import { EvidencePage } from "@/pages/EvidencePage";
import { EvidenceDetailPage } from "@/pages/EvidenceDetailPage";
import { EvidenceDbPage } from "@/pages/EvidenceDbPage";
import { PipelinePage } from "@/pages/PipelinePage";
import { PipelineRunPage } from "@/pages/PipelineRunPage";

export function App() {
  return (
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
  );
}
