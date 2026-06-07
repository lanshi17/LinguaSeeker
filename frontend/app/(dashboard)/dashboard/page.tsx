import { DashboardStats } from "@/features/dashboard";
import { PageHeader } from "@/components/layout/PageHeader";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Pipeline overview and evidence review statistics."
      />
      <DashboardStats />
    </div>
  );
}
