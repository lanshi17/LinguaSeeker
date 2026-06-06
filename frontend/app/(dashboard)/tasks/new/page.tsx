import { TaskUploadView } from "@/features/task-flow";
import { PageHeader } from "@/components/layout/PageHeader";

export default function TaskNewPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="New Task"
        description="Upload documents or submit URLs for processing."
      />
      <TaskUploadView />
    </div>
  );
}
