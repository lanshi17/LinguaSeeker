import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface PaperJudgmentCardProps {
  title: string;
  status: string;
  outcome?: string;
}

export function PaperJudgmentCard({
  title,
  status,
  outcome,
}: PaperJudgmentCardProps) {
  return (
    <Card>
      <h4 className="text-sm font-semibold text-gray-700">{title}</h4>
      <div className="mt-2 flex items-center gap-2">
        <Badge variant="info">{status}</Badge>
        {outcome && <span className="text-sm text-gray-600">{outcome}</span>}
      </div>
    </Card>
  );
}
