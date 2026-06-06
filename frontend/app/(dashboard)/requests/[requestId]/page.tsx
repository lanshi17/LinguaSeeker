import { PageHeader } from "@/components/layout/PageHeader";

interface RequestMonitorPageProps {
  params: Promise<{ requestId: string }>;
}

export default async function RequestMonitorPage({
  params,
}: RequestMonitorPageProps) {
  const { requestId } = await params;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Request Monitor"
        description={`Request ID: ${requestId}`}
      />
      <p className="text-sm text-gray-500">
        Pipeline status and per-paper monitoring will be rendered here.
      </p>
    </div>
  );
}
