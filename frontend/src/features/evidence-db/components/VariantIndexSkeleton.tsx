import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the VariantIndexView layout:
 * hero stats grid + search bar + variant list with staggered shimmer.
 */
export function VariantIndexSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Hero Stats Section */}
      <section
        className="edb-hero"
        style={{ borderRadius: 16, border: "1px solid var(--color-border)", padding: 24 }}
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
                border: "1px solid var(--color-bg-muted)",
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
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
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
            borderTop: "1px solid var(--color-bg-muted)",
            paddingTop: 12,
            marginTop: 12,
          }}
        >
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="pill" style={{ width: 64, height: 28 }} />
          ))}
        </div>
      </section>

      {/* Variant List */}
      <div
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: 12,
          overflow: "hidden",
          background: "var(--color-surface)",
        }}
      >
        {/* List header skeleton */}
        <div
          style={{
            display: "none",
            gridTemplateColumns: "2fr 1.5fr 120px 100px 100px 100px 120px 90px",
            alignItems: "center",
            gap: 8,
            padding: "10px 16px",
            backgroundColor: "var(--color-bg)",
            borderBottom: "1px solid var(--color-border)",
          }}
          className="skeleton-list-header"
        >
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} variant="text" style={{ width: 48, height: 10 }} />
          ))}
        </div>
        {/* List rows skeleton */}
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="stagger-in"
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1.5fr 120px 100px 100px 100px 120px 90px",
              alignItems: "center",
              gap: 8,
              padding: "14px 16px",
              borderBottom: i < 7 ? "1px solid var(--color-bg-muted)" : "none",
              animationDelay: `${(i + 4) * 50}ms`,
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <Skeleton variant="text" style={{ width: 120, height: 16 }} />
              <Skeleton variant="line" style={{ width: 80 }} />
            </div>
            <Skeleton variant="text" style={{ width: "80%" }} />
            <Skeleton variant="pill" style={{ width: 52, height: 20 }} />
            <Skeleton variant="line" style={{ width: 48 }} />
            <Skeleton variant="line" style={{ width: 40 }} />
            <Skeleton variant="line" style={{ width: 36 }} />
            <Skeleton variant="block" style={{ height: 4, borderRadius: 2 }} />
            <Skeleton variant="line" style={{ width: 60 }} />
          </div>
        ))}
      </div>

      {/* Responsive: show simpler skeleton on small screens */}
      <style>{`
        @media (min-width: 768px) {
          .skeleton-list-header {
            display: grid !important;
          }
        }
        @media (max-width: 767px) {
          .stagger-in[style*="grid-template-columns"] {
            display: flex !important;
            flex-direction: column !important;
            gap: 8px !important;
          }
        }
      `}</style>
    </div>
  );
}
