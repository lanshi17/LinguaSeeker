import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";

interface CategoryDistributionBarProps {
  distribution: Record<string, number>;
}

export function CategoryDistributionBar({ distribution }: CategoryDistributionBarProps) {
  const entries = Object.entries(distribution)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a);

  if (entries.length === 0) return null;

  const total = entries.reduce((sum, [, c]) => sum + c, 0);

  return (
    <div className="edb-cat-strip" style={{ display: "flex", width: "100%" }}>
      {entries.map(([cat, count]) => (
        <span
          key={cat}
          style={{
            backgroundColor: CATEGORY_COLORS[cat]?.hex ?? "#64748B",
            flexGrow: count / total,
          }}
          title={`Category ${cat}: ${count} fields`}
        />
      ))}
    </div>
  );
}
