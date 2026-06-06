import { Card } from "@/components/ui/Card";

interface EvidenceJudgmentPaneProps {
  rawData?: unknown;
}

export function EvidenceJudgmentPane({ rawData }: EvidenceJudgmentPaneProps) {
  if (!rawData) {
    return (
      <p className="py-10 text-center text-sm text-gray-500">
        No evidence data available.
      </p>
    );
  }

  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-gray-700">
        Evidence Data
      </h3>
      <pre className="max-h-[500px] overflow-auto rounded bg-gray-50 p-4 text-xs text-gray-800">
        {JSON.stringify(rawData, null, 2)}
      </pre>
    </Card>
  );
}
