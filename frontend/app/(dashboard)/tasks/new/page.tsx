import { PageHeader } from "@/components/layout/PageHeader";

export default function TaskNewPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="New Task"
        description="Fill in the structured task form and upload documents."
      />
      <p className="text-sm text-gray-500">
        TaskForm, FileUploadZone, and WebCrawlForm will be rendered here.
      </p>
    </div>
  );
}
