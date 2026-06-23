import { useMemo, useState } from "react";
import { Button, Input, Segmented, Flex, Typography } from "antd";
import { Search, ClipboardCheck } from "lucide-react";
import { MetricTile } from "@/components/ui/MetricTile";
import { useAuditEvents } from "../hooks/useAuditEvents";
import { AuditEventTable } from "./AuditEventTable";
import { AuditEventDetailDrawer } from "./AuditEventDetailDrawer";
import { EvidenceReviewDrawer } from "./EvidenceReviewDrawer";
import type { ReviewAuditEventResponse } from "../types/audit";

type StatusFilter = "all" | "approved" | "corrected" | "rejected";

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "approved", label: "Approved" },
  { value: "corrected", label: "Corrected" },
  { value: "rejected", label: "Rejected" },
];

export function AuditView() {
  const { data: events, isLoading } = useAuditEvents({ limit: 500 });
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<ReviewAuditEventResponse | null>(null);
  const [reviewDrawerOpen, setReviewDrawerOpen] = useState(false);

  const filtered = useMemo(() => {
    if (!events) return [];
    let result = events;

    if (statusFilter !== "all") {
      result = result.filter((e) => e.new_status === statusFilter);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.canonical_evidence_id.toLowerCase().includes(q) ||
          e.target_type.toLowerCase().includes(q) ||
          (e.change_reason?.toLowerCase().includes(q) ?? false) ||
          e.field_deltas.some((d) => d.field.toLowerCase().includes(q)),
      );
    }

    return result;
  }, [events, statusFilter, search]);

  const stats = useMemo(() => {
    if (!events) return { total: 0, approved: 0, corrected: 0, rejected: 0 };
    return {
      total: events.length,
      approved: events.filter((e) => e.new_status === "approved").length,
      corrected: events.filter((e) => e.new_status === "corrected").length,
      rejected: events.filter((e) => e.new_status === "rejected").length,
    };
  }, [events]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Summary stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
        }}
      >
        <MetricTile label="Total events" value={stats.total} tone="primary" />
        <MetricTile label="Approved" value={stats.approved} tone="success" />
        <MetricTile label="Corrected" value={stats.corrected} tone="warning" />
        <MetricTile label="Rejected" value={stats.rejected} tone="error" />
      </div>

      {/* Filters */}
      <Flex gap={12} align="center" wrap="wrap" justify="space-between">
        <Flex gap={12} align="center" wrap="wrap">
          <Segmented
            value={statusFilter}
            onChange={(val) => setStatusFilter(val as StatusFilter)}
            options={STATUS_FILTERS}
          />
          <Input
            placeholder="Search evidence ID, field, reason…"
            prefix={<Search style={{ width: 14, height: 14, color: "#9ca3af" }} />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ maxWidth: 320 }}
            allowClear
          />
          {filtered.length < (events?.length ?? 0) && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Showing {filtered.length} of {events?.length ?? 0}
            </Typography.Text>
          )}
        </Flex>
        <Button
          type="primary"
          icon={<ClipboardCheck style={{ width: 14, height: 14 }} />}
          onClick={() => setReviewDrawerOpen(true)}
        >
          Review Evidence
        </Button>
      </Flex>

      {/* Table */}
      <AuditEventTable
        events={filtered}
        loading={isLoading}
        onRowClick={setSelectedEvent}
      />

      {/* Detail drawer */}
      <AuditEventDetailDrawer
        event={selectedEvent}
        open={selectedEvent !== null}
        onClose={() => setSelectedEvent(null)}
      />

      {/* Evidence review drawer */}
      <EvidenceReviewDrawer
        open={reviewDrawerOpen}
        onClose={() => setReviewDrawerOpen(false)}
      />
    </div>
  );
}
