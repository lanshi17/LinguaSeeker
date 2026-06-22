import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the BilingualEvidenceView layout:
 * breadcrumb + literature header + sidebar/reader two-column grid.
 */
export function BilingualEvidenceSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Skeleton variant="line" style={{ width: 80 }} />
        <Skeleton variant="circle" style={{ width: 14, height: 14 }} />
        <Skeleton variant="line" style={{ width: 112 }} />
        <Skeleton variant="circle" style={{ width: 14, height: 14 }} />
        <Skeleton variant="line" style={{ width: 160 }} />
      </div>

      {/* Literature Header */}
      <section
        style={{
          borderRadius: 12,
          border: "1px solid #e5e7eb",
          backgroundColor: "#fff",
          padding: 20,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
          <Skeleton
            variant="block"
            style={{ width: 40, height: 40, borderRadius: 8, flexShrink: 0 }}
          />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
            <Skeleton variant="text" style={{ width: "75%", height: 20 }} />
            <div style={{ display: "flex", gap: 12 }}>
              <Skeleton variant="line" style={{ width: 96 }} />
              <Skeleton variant="line" style={{ width: 128 }} />
              <Skeleton variant="line" style={{ width: 112 }} />
            </div>
          </div>
        </div>
      </section>

      {/* Two-column: sidebar + reader */}
      <div
        style={{
          display: "grid",
          gap: 20,
          gridTemplateColumns: "280px minmax(0, 1fr)",
        }}
      >
        {/* Sidebar */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="edb-card" style={{ borderRadius: 12, padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
            <Skeleton variant="line" style={{ width: 96, height: 12 }} />
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <Skeleton variant="text" style={{ width: 112 }} />
                <Skeleton variant="pill" style={{ width: 24, height: 16 }} />
              </div>
            ))}
          </div>
          <div className="edb-card" style={{ borderRadius: 12, padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
            <Skeleton variant="line" style={{ width: 96, height: 12 }} />
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} variant="text" style={{ width: "100%", height: 32 }} />
            ))}
          </div>
        </aside>

        {/* Main: bilingual panels */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Active evidence card */}
          <div
            style={{
              borderRadius: 12,
              border: "1px solid #e5e7eb",
              backgroundColor: "#fff",
              padding: 16,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <Skeleton variant="text" style={{ width: "50%", height: 20 }} />
            <Skeleton variant="text" style={{ width: "100%" }} />
            <Skeleton variant="text" style={{ width: "75%" }} />
          </div>

          {/* Bilingual reader panels */}
          <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(2, 1fr)" }}>
            {Array.from({ length: 2 }).map((_, i) => (
              <div
                key={i}
                className="stagger-in"
                style={{
                  borderRadius: 12,
                  border: "1px solid #e5e7eb",
                  backgroundColor: "#fff",
                  padding: 20,
                  animationDelay: `${i * 80}ms`,
                }}
              >
                <Skeleton variant="text" style={{ width: 112, height: 20, marginBottom: 16 }} />
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {Array.from({ length: 5 }).map((_, j) => (
                    <Skeleton key={j} variant="text" style={{ width: "100%" }} />
                  ))}
                  <Skeleton variant="text" style={{ width: "66%" }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
