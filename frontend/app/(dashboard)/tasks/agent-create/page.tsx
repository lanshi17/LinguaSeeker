import { TaskCreateView } from "@/features/task-flow";
import { PageHeader } from "@/components/layout/PageHeader";

export default function AgentCreatePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Task Creation"
        description="Define your research goal and interact with the ACMG Agent."
      />
      <TaskCreateView />
    </div>
  );
}
