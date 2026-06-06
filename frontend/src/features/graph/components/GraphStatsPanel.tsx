"use client";

import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

interface GraphStatsPanelProps {
  stats?: Record<string, unknown>;
  onLoad: () => void;
  isLoading?: boolean;
}

export function GraphStatsPanel({
  stats,
  onLoad,
  isLoading,
}: GraphStatsPanelProps) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">Graph Stats</h3>
        <Button size="sm" variant="ghost" onClick={onLoad} loading={isLoading}>
          Refresh
        </Button>
      </div>
      {isLoading && !stats && <Spinner size="sm" className="mt-3" />}
      {stats && (
        <pre className="mt-3 max-h-48 overflow-auto rounded bg-gray-50 p-3 text-xs text-gray-700">
          {JSON.stringify(stats, null, 2)}
        </pre>
      )}
    </Card>
  );
}
