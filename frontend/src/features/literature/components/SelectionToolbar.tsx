import { Button } from "@/components/ui/Button";

interface SelectionToolbarProps {
  selectedCount: number;
  onSubmit: () => void;
  isSubmitting?: boolean;
}

export function SelectionToolbar({
  selectedCount,
  onSubmit,
  isSubmitting,
}: SelectionToolbarProps) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-sm text-gray-600">
        {selectedCount} paper{selectedCount !== 1 ? "s" : ""} selected
      </p>
      <Button
        onClick={onSubmit}
        disabled={selectedCount === 0}
        loading={isSubmitting}
      >
        Submit Selection
      </Button>
    </div>
  );
}
