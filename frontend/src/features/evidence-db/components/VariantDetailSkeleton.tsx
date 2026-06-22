import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the VariantDetailView layout:
 * back link + hero section + two-column evidence/references grid.
 */
export function VariantDetailSkeleton() {
  return (
    <div className="space-y-6">
      {/* Back link */}
      <Skeleton variant="line" width="w-40" height="h-4" />

      {/* Variant Hero */}
      <section className="edb-hero rounded-2xl border border-gray-200 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Skeleton variant="text" width="w-20" height="h-6" />
              <Skeleton variant="pill" width="w-24" height="h-6" />
            </div>
            <Skeleton variant="text" width="w-48" height="h-5" />
            <Skeleton variant="line" width="w-36" />
          </div>
          <div className="flex items-center gap-4">
            <Skeleton variant="circle" width="w-14" height="h-14" />
            <div className="grid grid-cols-2 gap-x-6 gap-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-1">
                  <Skeleton variant="text" width="w-10" height="h-5" />
                  <Skeleton variant="line" width="w-20" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Main: Evidence Fields */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Skeleton variant="text" width="w-28" height="h-5" />
            <Skeleton variant="line" width="w-32" />
          </div>
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="stagger-in rounded-xl border border-gray-200 bg-white p-4"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <Skeleton variant="text" width="w-24" height="h-5" className="mb-3" />
                <div className="space-y-2">
                  <Skeleton variant="text" width="w-full" />
                  <Skeleton variant="text" width="w-3/4" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sidebar: References */}
        <aside className="space-y-4">
          <div className="flex items-center justify-between">
            <Skeleton variant="text" width="w-20" height="h-5" />
            <Skeleton variant="line" width="w-16" />
          </div>
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="stagger-in rounded-lg border border-gray-200 bg-white p-3"
                style={{ animationDelay: `${(i + 3) * 60}ms` }}
              >
                <Skeleton variant="text" width="w-full" className="mb-2" />
                <Skeleton variant="line" width="w-3/4" />
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
