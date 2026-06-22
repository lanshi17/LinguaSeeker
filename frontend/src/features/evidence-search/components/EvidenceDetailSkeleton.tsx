import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the EvidenceDetailView / LiteratureOverview:
 * back link + literature hero card + sidebar/main two-column grid.
 */
export function EvidenceDetailSkeleton() {
  return (
    <div className="space-y-5">
      {/* Back link */}
      <Skeleton variant="line" width="w-32" height="h-4" />

      {/* Literature hero card */}
      <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-100 bg-gray-50/50 px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex-1 space-y-3">
              <Skeleton variant="line" width="w-28" />
              <Skeleton variant="text" width="w-3/4" height="h-6" />
              <div className="flex gap-2">
                <Skeleton variant="pill" width="w-32" />
                <Skeleton variant="pill" width="w-24" />
                <Skeleton variant="pill" width="w-28" />
              </div>
            </div>
            <Skeleton variant="pill" width="w-20" height="h-6" />
          </div>
        </div>

        <div className="grid gap-0 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="border-b border-gray-100 px-5 py-4 md:border-b-0 md:border-r last:md:border-r-0"
            >
              <Skeleton variant="line" width="w-16" className="mb-2" />
              <Skeleton variant="text" width="w-24" height="h-5" />
            </div>
          ))}
        </div>
      </section>

      {/* Two-column: sidebar + main */}
      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* Sidebar */}
        <aside className="space-y-5">
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-4">
            <Skeleton variant="text" width="w-32" height="h-5" />
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-1">
                  <Skeleton variant="text" width="w-12" height="h-6" />
                  <Skeleton variant="line" width="w-16" />
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
            <Skeleton variant="text" width="w-28" height="h-5" />
            <div className="edb-cat-strip">
              <Skeleton variant="block" height="h-1" className="flex-1 rounded-sm" />
            </div>
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between">
                <Skeleton variant="text" width="w-24" />
                <Skeleton variant="pill" width="w-8" height="h-4" />
              </div>
            ))}
          </div>
        </aside>

        {/* Main: evidence items */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Skeleton variant="text" width="w-32" height="h-5" />
            <Skeleton variant="line" width="w-20" />
          </div>
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="stagger-in rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <Skeleton variant="text" width="w-1/3" height="h-5" className="mb-3" />
              <div className="space-y-2">
                <Skeleton variant="text" width="w-full" />
                <Skeleton variant="text" width="w-5/6" />
                <Skeleton variant="text" width="w-2/3" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
