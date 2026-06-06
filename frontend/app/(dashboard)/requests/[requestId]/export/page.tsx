import { DocumentViewer } from "@/features/document-viewer";
import { PageHeader } from "@/components/layout/PageHeader";

interface ExportPageProps {
  params: Promise<{ requestId: string }>;
}

export default async function ExportPage({ params }: ExportPageProps) {
  const { requestId } = await params;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Export"
        description={`Export results for request ${requestId}`}
      />
      <DocumentViewer documentId={requestId} />
    </div>
  );
}
