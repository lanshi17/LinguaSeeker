import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the EvidenceResultsTable layout:
 * header bar + 5 table rows with staggered shimmer.
 */
export function EvidenceTableSkeleton() {
  return (
    <div className="space-y-4">
      {/* Header skeleton */}
      <div className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm">
        <Skeleton variant="block" width="w-10" height="h-10" className="rounded-lg shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton variant="text" width="w-40" />
          <Skeleton variant="line" width="w-56" />
        </div>
        <Skeleton variant="pill" width="w-24" height="h-8" />
      </div>

      {/* Desktop table skeleton */}
      <div className="hidden overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm md:block">
        {/* Table header */}
        <div className="flex border-b border-gray-200 bg-gray-50 px-4 py-3">
          {["w-[20%]", "w-[18%]", "w-[16%]", "w-[14%]", "w-[10%]", "w-[10%]", "w-[8%]"].map(
            (w, i) => (
              <div key={i} className={`${w} px-4`}>
                <Skeleton variant="line" width="w-16" />
              </div>
            ),
          )}
        </div>

        {/* Table rows */}
        {Array.from({ length: 5 }).map((_, row) => (
          <div
            key={row}
            className="stagger-in flex items-center border-b border-gray-100 px-4 py-4 last:border-b-0"
            style={{ animationDelay: `${row * 60}ms` }}
          >
            {/* Literature column */}
            <div className="w-[20%] px-4">
              <div className="flex items-start gap-3">
                <Skeleton variant="block" width="w-10" height="h-10" className="rounded-lg shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton variant="text" width="w-full" />
                  <Skeleton variant="line" width="w-20" />
                </div>
              </div>
            </div>
            {/* Evidence Focus */}
            <div className="w-[18%] px-4 space-y-2">
              <Skeleton variant="pill" width="w-16" />
              <Skeleton variant="pill" width="w-20" />
            </div>
            {/* Disease */}
            <div className="w-[16%] px-4">
              <Skeleton variant="text" width="w-full" />
            </div>
            {/* Classification */}
            <div className="w-[14%] px-4">
              <Skeleton variant="pill" width="w-14" />
            </div>
            {/* Created */}
            <div className="w-[10%] px-4">
              <Skeleton variant="line" width="w-20" />
            </div>
            {/* Review */}
            <div className="w-[10%] px-4">
              <Skeleton variant="pill" width="w-16" />
            </div>
            {/* Fields */}
            <div className="w-[8%] px-4 flex justify-end">
              <Skeleton variant="pill" width="w-8" />
            </div>
          </div>
        ))}
      </div>

      {/* Mobile card skeleton */}
      <div className="space-y-3 md:hidden">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="stagger-in rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <div className="flex items-start gap-3">
              <Skeleton variant="block" width="w-11" height="h-11" className="rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton variant="text" width="w-full" />
                <Skeleton variant="line" width="w-24" />
              </div>
              <Skeleton variant="pill" width="w-16" />
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex gap-2">
                <Skeleton variant="pill" width="w-16" />
                <Skeleton variant="pill" width="w-20" />
              </div>
              <Skeleton variant="text" width="w-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
