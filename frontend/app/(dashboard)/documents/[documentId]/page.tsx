import { DocumentViewer } from "@/features/document-viewer";
import { PageHeader } from "@/components/layout/PageHeader";

interface DocumentPageProps {
  params: Promise<{ documentId: string }>;
}

export default async function DocumentPage({ params }: DocumentPageProps) {
  const { documentId } = await params;

  return (
    <div className="space-y-6">
      <PageHeader title="Document Viewer" description={documentId} />
      <DocumentViewer documentId={documentId} />
    </div>
  );
}
