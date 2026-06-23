import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Structural skeleton matching the EvidenceDetailView / LiteratureOverview:
 * back link + literature hero card + sidebar/main two-column grid.
 */
export function EvidenceDetailSkeleton() {
  return (
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Back link */}
        <Skeleton variant="line" style={{ width: 128, height: 16 }} />

        {/* Literature hero card */}
        <section style={{ overflow: "hidden", borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}>
          <div style={{ borderBottom: "1px solid #f3f4f6", backgroundColor: "rgba(249,250,251,0.5)", padding: "20px 24px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
                <Skeleton variant="line" style={{ width: 112 }} />
                <Skeleton variant="text" style={{ width: "75%", height: 24 }} />
                <div style={{ display: "flex", gap: 8 }}>
                  <Skeleton variant="pill" style={{ width: 128 }} />
                  <Skeleton variant="pill" style={{ width: 96 }} />
                  <Skeleton variant="pill" style={{ width: 112 }} />
                </div>
              </div>
              <Skeleton variant="pill" style={{ width: 80, height: 24 }} />
            </div>
          </div>

          <div className="eds-meta-grid">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="eds-meta-cell">
                <Skeleton variant="line" style={{ width: 64, marginBottom: 8 }} />
                <Skeleton variant="text" style={{ width: 96, height: 20 }} />
              </div>
            ))}
          </div>
        </section>

        {/* Two-column: sidebar + main */}
        <div className="eds-two-col">
          {/* Sidebar */}
          <aside style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", padding: 20, boxShadow: "0 1px 2px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", gap: 16 }}>
              <Skeleton variant="text" style={{ width: 128, height: 20 }} />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <Skeleton variant="text" style={{ width: 48, height: 24 }} />
                    <Skeleton variant="line" style={{ width: 64 }} />
                  </div>
                ))}
              </div>
            </div>
            <div style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", padding: 20, boxShadow: "0 1px 2px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", gap: 12 }}>
              <Skeleton variant="text" style={{ width: 112, height: 20 }} />
              <div className="edb-cat-strip">
                <Skeleton variant="block" style={{ height: 4, flex: 1, borderRadius: 2 }} />
              </div>
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <Skeleton variant="text" style={{ width: 96 }} />
                  <Skeleton variant="pill" style={{ width: 32, height: 16 }} />
                </div>
              ))}
            </div>
          </aside>

          {/* Main: evidence items */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Skeleton variant="text" style={{ width: 128, height: 20 }} />
              <Skeleton variant="line" style={{ width: 80 }} />
            </div>
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="stagger-in"
                style={{
                  borderRadius: 12,
                  border: "1px solid #e5e7eb",
                  backgroundColor: "#fff",
                  padding: 20,
                  boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                  animationDelay: `${i * 60}ms`,
                }}
              >
                <Skeleton variant="text" style={{ width: "33%", height: 20, marginBottom: 12 }} />
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <Skeleton variant="text" style={{ width: "100%" }} />
                  <Skeleton variant="text" style={{ width: "83%" }} />
                  <Skeleton variant="text" style={{ width: "67%" }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
  );
}
