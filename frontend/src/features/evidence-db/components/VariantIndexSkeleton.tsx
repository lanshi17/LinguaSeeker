import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the VariantIndexView layout:
 * hero stats grid + search bar + variant card grid with staggered shimmer.
 */
export function VariantIndexSkeleton() {
  return (
    <div className="space-y-6">
      {/* Hero Stats Section */}
      <section className="edb-hero rounded-2xl border border-gray-200 p-6">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="stagger-in flex items-center gap-3 rounded-lg border border-gray-100 bg-gray-50/60 px-4 py-3"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <Skeleton variant="block" width="w-9" height="h-9" className="rounded-lg shrink-0" />
              <div className="space-y-1.5">
                <Skeleton variant="text" width="w-12" height="h-5" />
                <Skeleton variant="line" width="w-20" />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Search & Filter Bar */}
      <section className="rounded-xl border border-gray-200 bg-white p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Skeleton variant="pill" width="w-full" height="h-10" className="flex-1" />
          <Skeleton variant="pill" width="w-48" height="h-10" />
        </div>
        <div className="mt-3 flex gap-1.5 border-t border-gray-100 pt-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="pill" width="w-16" height="h-7" />
          ))}
        </div>
      </section>

      {/* Variant Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="stagger-in"
            style={{ animationDelay: `${(i + 4) * 50}ms` }}
          >
            <div className="edb-card rounded-xl overflow-hidden">
              <Skeleton variant="block" height="h-0.5" className="rounded-none" />
              <div className="p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1.5">
                    <Skeleton variant="text" width="w-24" height="h-5" />
                    <Skeleton variant="line" width="w-32" />
                  </div>
                  <Skeleton variant="pill" width="w-10" height="h-5" />
                </div>
                <Skeleton variant="text" width="w-full" />
                <Skeleton variant="line" width="w-28" />
                <div className="flex items-center gap-4">
                  <Skeleton variant="line" width="w-16" />
                  <Skeleton variant="line" width="w-14" />
                  <Skeleton variant="line" width="w-12" />
                </div>
                <Skeleton variant="block" height="h-1" className="rounded-sm" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
