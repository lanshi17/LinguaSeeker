import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the BilingualEvidenceView layout:
 * breadcrumb + literature header + sidebar/reader two-column grid.
 */
export function BilingualEvidenceSkeleton() {
  return (
    <div className="space-y-5">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5">
        <Skeleton variant="line" width="w-20" />
        <Skeleton variant="circle" width="w-3.5" height="h-3.5" />
        <Skeleton variant="line" width="w-28" />
        <Skeleton variant="circle" width="w-3.5" height="h-3.5" />
        <Skeleton variant="line" width="w-40" />
      </div>

      {/* Literature Header */}
      <section className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="flex items-start gap-4">
          <Skeleton variant="block" width="w-10" height="h-10" className="rounded-lg shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" width="w-3/4" height="h-5" />
            <div className="flex gap-3">
              <Skeleton variant="line" width="w-24" />
              <Skeleton variant="line" width="w-32" />
              <Skeleton variant="line" width="w-28" />
            </div>
          </div>
        </div>
      </section>

      {/* Two-column: sidebar + reader */}
      <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        {/* Sidebar */}
        <aside className="space-y-4">
          <div className="edb-card rounded-xl p-4 space-y-3">
            <Skeleton variant="line" width="w-24" height="h-3" />
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between">
                <Skeleton variant="text" width="w-28" />
                <Skeleton variant="pill" width="w-6" height="h-4" />
              </div>
            ))}
          </div>
          <div className="edb-card rounded-xl p-4 space-y-2">
            <Skeleton variant="line" width="w-24" height="h-3" />
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} variant="text" width="w-full" height="h-8" />
            ))}
          </div>
        </aside>

        {/* Main: bilingual panels */}
        <div className="space-y-4">
          {/* Active evidence card */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-2">
            <Skeleton variant="text" width="w-1/2" height="h-5" />
            <Skeleton variant="text" width="w-full" />
            <Skeleton variant="text" width="w-3/4" />
          </div>

          {/* Bilingual reader panels */}
          <div className="grid gap-4 lg:grid-cols-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div
                key={i}
                className="stagger-in rounded-xl border border-gray-200 bg-white p-5"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <Skeleton variant="text" width="w-28" height="h-5" className="mb-4" />
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, j) => (
                    <Skeleton key={j} variant="text" width="w-full" />
                  ))}
                  <Skeleton variant="text" width="w-2/3" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
