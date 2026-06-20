import { Routes, Route, Navigate } from "react-router-dom";
import { AuthGuard } from "@/components/AuthGuard";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ChatPage } from "@/pages/ChatPage";
import { ChatSessionPage } from "@/pages/ChatSessionPage";
import { EvidencePage } from "@/pages/EvidencePage";
import { EvidenceDetailPage } from "@/pages/EvidenceDetailPage";
import { EvidenceDbPage } from "@/pages/EvidenceDbPage";
import { PipelinePage } from "@/pages/PipelinePage";
import { PipelineRunPage } from "@/pages/PipelineRunPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";

export function App() {
  return (
    <Routes>
      <Route index element={<Navigate to="/chat" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<AuthGuard><DashboardLayout /></AuthGuard>}>
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/chat/:sessionId" element={<ChatSessionPage />} />
        <Route path="/evidence" element={<EvidencePage />} />
        <Route path="/evidence/detail" element={<EvidenceDetailPage />} />
        <Route path="/evidence-db" element={<EvidenceDbPage />} />
        <Route path="/pipeline" element={<PipelinePage />} />
        <Route path="/pipeline/:runId" element={<PipelineRunPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
