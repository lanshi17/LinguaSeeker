import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the VariantDetailView layout:
 * back link + hero section + two-column evidence/references grid.
 */
export function VariantDetailSkeleton() {
  return (
    <>
      <style>{`
        .vds-layout { display: grid; gap: 24px; }
        .vds-hero-inner { display: flex; flex-direction: column; gap: 16px; }
        .vds-stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); column-gap: 24px; row-gap: 8px; }
        .vds-two-col { display: grid; gap: 24px; }
        @media (min-width: 1024px) {
          .vds-hero-inner { flex-direction: row; align-items: flex-start; justify-content: space-between; }
          .vds-two-col { grid-template-columns: minmax(0, 1fr) 340px; }
        }
      `}</style>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Back link */}
        <Skeleton variant="line" style={{ width: 160, height: 16 }} />

        {/* Variant Hero */}
        <section className="edb-hero" style={{ borderRadius: 16, border: "1px solid #e5e7eb", padding: 24 }}>
          <div className="vds-hero-inner">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <Skeleton variant="text" style={{ width: 80, height: 24 }} />
                <Skeleton variant="pill" style={{ width: 96, height: 24 }} />
              </div>
              <Skeleton variant="text" style={{ width: 192, height: 20 }} />
              <Skeleton variant="line" style={{ width: 144 }} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <Skeleton variant="circle" style={{ width: 56, height: 56 }} />
              <div className="vds-stats-grid">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <Skeleton variant="text" style={{ width: 40, height: 20 }} />
                    <Skeleton variant="line" style={{ width: 80 }} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Two-column layout */}
        <div className="vds-two-col">
          {/* Main: Evidence Fields */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Skeleton variant="text" style={{ width: 112, height: 20 }} />
              <Skeleton variant="line" style={{ width: 128 }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="stagger-in"
                  style={{
                    borderRadius: 12,
                    border: "1px solid #e5e7eb",
                    backgroundColor: "#fff",
                    padding: 16,
                    animationDelay: `${i * 60}ms`,
                  }}
                >
                  <Skeleton variant="text" style={{ width: 96, height: 20, marginBottom: 12 }} />
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <Skeleton variant="text" style={{ width: "100%" }} />
                    <Skeleton variant="text" style={{ width: "75%" }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Sidebar: References */}
          <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Skeleton variant="text" style={{ width: 80, height: 20 }} />
              <Skeleton variant="line" style={{ width: 64 }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="stagger-in"
                  style={{
                    borderRadius: 8,
                    border: "1px solid #e5e7eb",
                    backgroundColor: "#fff",
                    padding: 12,
                    animationDelay: `${(i + 3) * 60}ms`,
                  }}
                >
                  <Skeleton variant="text" style={{ width: "100%", marginBottom: 8 }} />
                  <Skeleton variant="line" style={{ width: "75%" }} />
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </>
  );
}
