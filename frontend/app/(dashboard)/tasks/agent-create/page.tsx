import { PageHeader } from "@/components/layout/PageHeader";

export default function AgentCreatePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Task Creation"
        description="Define your research goal and interact with the ACMG Agent."
      />
      <p className="text-sm text-gray-500">
        Agent clarification chat will be rendered here using the task-flow feature.
      </p>
    </div>
  );
}
