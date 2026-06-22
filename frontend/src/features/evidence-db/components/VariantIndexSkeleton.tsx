import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the VariantIndexView layout:
 * hero stats grid + search bar + variant card grid with staggered shimmer.
 */
export function VariantIndexSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Hero Stats Section */}
      <section
        className="edb-hero"
        style={{ borderRadius: 16, border: "1px solid #e5e7eb", padding: 24 }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="stagger-in"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                borderRadius: 8,
                border: "1px solid #f3f4f6",
                backgroundColor: "rgba(249, 250, 251, 0.6)",
                padding: "12px 16px",
                animationDelay: `${i * 50}ms`,
              }}
            >
              <Skeleton
                variant="block"
                style={{ width: 36, height: 36, borderRadius: 8, flexShrink: 0 }}
              />
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <Skeleton variant="text" style={{ width: 48, height: 20 }} />
                <Skeleton variant="line" style={{ width: 80 }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Search & Filter Bar */}
      <section
        style={{
          borderRadius: 12,
          border: "1px solid #e5e7eb",
          backgroundColor: "#fff",
          padding: 16,
        }}
      >
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Skeleton variant="pill" style={{ flex: 1, height: 40 }} />
          <Skeleton variant="pill" style={{ width: 192, height: 40 }} />
        </div>
        <div
          style={{
            display: "flex",
            gap: 6,
            borderTop: "1px solid #f3f4f6",
            paddingTop: 12,
            marginTop: 12,
          }}
        >
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="pill" style={{ width: 64, height: 28 }} />
          ))}
        </div>
      </section>

      {/* Variant Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="stagger-in"
            style={{ animationDelay: `${(i + 4) * 50}ms` }}
          >
            <div className="edb-card" style={{ borderRadius: 12, overflow: "hidden" }}>
              <Skeleton variant="block" style={{ height: 2, borderRadius: 0 }} />
              <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <Skeleton variant="text" style={{ width: 96, height: 20 }} />
                    <Skeleton variant="line" style={{ width: 128 }} />
                  </div>
                  <Skeleton variant="pill" style={{ width: 40, height: 20 }} />
                </div>
                <Skeleton variant="text" style={{ width: "100%" }} />
                <Skeleton variant="line" style={{ width: 112 }} />
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <Skeleton variant="line" style={{ width: 64 }} />
                  <Skeleton variant="line" style={{ width: 56 }} />
                  <Skeleton variant="line" style={{ width: 48 }} />
                </div>
                <Skeleton variant="block" style={{ height: 4, borderRadius: 2 }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
