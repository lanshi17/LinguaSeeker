import { Skeleton } from "@/components/ui/Skeleton";

const COL_WIDTHS = ["20%", "18%", "16%", "14%", "10%", "10%", "8%"];

/**
 * Structural skeleton matching the EvidenceResultsTable layout:
 * header bar + 5 table rows with staggered shimmer.
 */
export function EvidenceTableSkeleton() {
  return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Header skeleton */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          borderRadius: 12,
          border: "1px solid #e5e7eb",
          backgroundColor: "#fff",
          padding: "16px 20px",
          boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
        }}>
          <Skeleton variant="block" style={{ width: 40, height: 40, borderRadius: 8, flexShrink: 0 }} />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
            <Skeleton variant="text" style={{ width: 160 }} />
            <Skeleton variant="line" style={{ width: 224 }} />
          </div>
          <Skeleton variant="pill" style={{ width: 96, height: 32 }} />
        </div>

        {/* Desktop table skeleton */}
        <div className="ets-desktop" style={{
          overflow: "hidden",
          borderRadius: 12,
          border: "1px solid #e5e7eb",
          backgroundColor: "#fff",
          boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
        }}>
          {/* Table header */}
          <div style={{
            display: "flex",
            borderBottom: "1px solid #e5e7eb",
            backgroundColor: "#f9fafb",
            padding: "12px 16px",
          }}>
            {COL_WIDTHS.map((w, i) => (
              <div key={i} style={{ width: w, padding: "0 16px" }}>
                <Skeleton variant="line" style={{ width: 64 }} />
              </div>
            ))}
          </div>

          {/* Table rows */}
          {Array.from({ length: 5 }).map((_, row) => (
            <div
              key={row}
              className="stagger-in"
              style={{
                display: "flex",
                alignItems: "center",
                borderBottom: row < 4 ? "1px solid #f3f4f6" : "none",
                padding: "16px",
                animationDelay: `${row * 60}ms`,
              }}
            >
              {/* Literature column */}
              <div style={{ width: "20%", padding: "0 16px" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                  <Skeleton variant="block" style={{ width: 40, height: 40, borderRadius: 8, flexShrink: 0 }} />
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
                    <Skeleton variant="text" style={{ width: "100%" }} />
                    <Skeleton variant="line" style={{ width: 80 }} />
                  </div>
                </div>
              </div>
              {/* Evidence Focus */}
              <div style={{ width: "18%", padding: "0 16px", display: "flex", flexDirection: "column", gap: 8 }}>
                <Skeleton variant="pill" style={{ width: 64 }} />
                <Skeleton variant="pill" style={{ width: 80 }} />
              </div>
              {/* Disease */}
              <div style={{ width: "16%", padding: "0 16px" }}>
                <Skeleton variant="text" style={{ width: "100%" }} />
              </div>
              {/* Classification */}
              <div style={{ width: "14%", padding: "0 16px" }}>
                <Skeleton variant="pill" style={{ width: 56 }} />
              </div>
              {/* Created */}
              <div style={{ width: "10%", padding: "0 16px" }}>
                <Skeleton variant="line" style={{ width: 80 }} />
              </div>
              {/* Review */}
              <div style={{ width: "10%", padding: "0 16px" }}>
                <Skeleton variant="pill" style={{ width: 64 }} />
              </div>
              {/* Fields */}
              <div style={{ width: "8%", padding: "0 16px", display: "flex", justifyContent: "flex-end" }}>
                <Skeleton variant="pill" style={{ width: 32 }} />
              </div>
            </div>
          ))}
        </div>

        {/* Mobile card skeleton */}
        <div className="ets-mobile" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="stagger-in"
              style={{
                borderRadius: 12,
                border: "1px solid #e5e7eb",
                backgroundColor: "#fff",
                padding: 16,
                boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                animationDelay: `${i * 60}ms`,
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <Skeleton variant="block" style={{ width: 44, height: 44, borderRadius: 8, flexShrink: 0 }} />
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
                  <Skeleton variant="text" style={{ width: "100%" }} />
                  <Skeleton variant="line" style={{ width: 96 }} />
                </div>
                <Skeleton variant="pill" style={{ width: 64 }} />
              </div>
              <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <Skeleton variant="pill" style={{ width: 64 }} />
                  <Skeleton variant="pill" style={{ width: 80 }} />
                </div>
                <Skeleton variant="text" style={{ width: "100%" }} />
              </div>
            </div>
          ))}
        </div>
      </div>
  );
}
