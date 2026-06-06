import { AuditEventList } from "@/features/delta-audit";
import { PageHeader } from "@/components/layout/PageHeader";

export default function AuditPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Delta Audit Trail"
        description="Review history of evidence card changes."
      />
      <AuditEventList />
    </div>
  );
}
