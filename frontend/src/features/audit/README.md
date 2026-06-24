# Audit Feature

> Review and inspect Phase 4 evidence corrections, status changes, and field-level audit deltas.

## Quick Start

```tsx
import { AuditView } from "@/features/audit";

export function AuditPage() {
  return <AuditView />;
}
```

`AuditView` fetches recent audit events, renders summary metrics and a table, opens event details, and provides the `EvidenceReviewDrawer` entry point for correcting stored evidence.

## Structure

```
features/audit/
|-- index.ts                          # Barrel exports
|-- components/
|   |-- AuditView.tsx                 # Page-level orchestrator: metrics, filters, table, drawers
|   |-- AuditEventTable.tsx           # antd Table with status transitions, field changes, reasons
|   |-- AuditEventDetailDrawer.tsx    # Drawer showing event metadata and field-level old/new values
|   +-- EvidenceReviewDrawer.tsx      # Search evidence, edit fields, submit status/value corrections
|-- hooks/
|   +-- useAuditEvents.ts            # React Query hook polling audit events (10s interval)
|-- services/
|   +-- audit.ts                     # listAuditEvents() -> GET /api/v1/delta-audit/
|-- types/
|   +-- audit.ts                     # AuditEventQuery, DeltaEntry, ReviewStatusValue, ReviewAuditEventResponse
+-- utils/
    +-- reviewPatch.ts               # cardFieldForFieldId(), buildReviewPatchOperations()
```

## Architecture

```text
AuditPage
  -> AuditView
      -> useAuditEvents()
          -> GET /api/v1/delta-audit/
      -> AuditEventTable
      -> AuditEventDetailDrawer
      -> EvidenceReviewDrawer
          -> searchEvidence()            (from @/api/evidence)
          -> getEvidenceGroupDetail()    (from @/api/evidence)
          -> buildReviewPatchOperations()
          -> PATCH /api/v1/evidence/{canonical_evidence_id}
          -> invalidate ["audit", "events"]
```

## Public API

### Components

| Export | Signature | Description |
| --- | --- | --- |
| `AuditView` | `function AuditView(): JSX.Element` | Page-level orchestrator for audit metrics, filters, table, detail drawer, and evidence review drawer. |
| `AuditEventTable` | `function AuditEventTable({ events, loading, onRowClick }): JSX.Element` | Displays audit events with status transitions, field-change counts, reasons, and row click selection. |
| `AuditEventDetailDrawer` | `function AuditEventDetailDrawer({ event, open, onClose }): JSX.Element \| null` | Shows event metadata and field-level old/new values with diff-style rendering. |
| `EvidenceReviewDrawer` | `function EvidenceReviewDrawer({ open, onClose }): JSX.Element` | Searches evidence groups by gene/variant/disease, lets reviewers edit mapped fields, submits status and value corrections, and refreshes audit events. |

### Hooks and Services

| Export | Signature | Description |
| --- | --- | --- |
| `useAuditEvents` | `function useAuditEvents(query?: AuditEventQuery)` | React Query hook polling audit event lists every 10s. Query key includes all filter params. |
| `listAuditEvents` | `async function listAuditEvents(query?): Promise<ReviewAuditEventResponse[]>` | Calls `GET /api/v1/delta-audit/` with optional filters (canonical_evidence_id, source_document_id, reviewer_id, limit). |

### Types

| Type | Description |
| --- | --- |
| `AuditEventQuery` | Query params: `canonical_evidence_id?`, `source_document_id?`, `reviewer_id?`, `limit?` |
| `DeltaEntry` | Field-level change: `field`, `old_value`, `new_value` |
| `ReviewStatusValue` | `"provisional" \| "approved" \| "corrected" \| "rejected"` |
| `ReviewAuditEventResponse` | Full audit event: `review_event_id`, `canonical_evidence_id`, `reviewer_id`, `target_type`, `old_status`, `new_status`, `field_deltas`, `change_reason`, `created_at` |
| `ReviewPatchOperation` | Output of `buildReviewPatchOperations`: `canonicalEvidenceId` + `body` |

### Patch Utilities

| Export | Signature | Description |
| --- | --- | --- |
| `cardFieldForFieldId` | `(fieldId: string) => string \| null` | Maps Phase 4 field IDs (e.g. `A.gene_symbol`) to backend card fields (e.g. `gene`). Returns null for unmapped fields. |
| `buildReviewPatchOperations` | `(args) => ReviewPatchOperation[]` | Converts field-level group edits into `PATCH /evidence/{id}` operations. Unmapped fields become status-only updates. |

## Field Mapping

The backend accepts only card-level patch fields:

| Field ID | Card field |
| --- | --- |
| `A.gene_symbol` | `gene` |
| `B.disease_diagnosis` | `disease` |
| `B.clinical_diagnosis` | `disease` |
| `J.authority_classification` | `classification` |
| `A.variant_hgvs_*` | `variant` |
| `A.variant_legacy_name` | `variant` |

Unmapped fields can still be approved, corrected, or rejected as status-only reviews. Their value input is disabled in `EvidenceReviewDrawer`.

## Data Flow

1. `AuditView` loads audit events with `useAuditEvents({ limit: 500 })`.
2. Users filter by status (segmented control) or search local event fields.
3. `EvidenceReviewDrawer` searches evidence by gene, variant, or disease.
4. Selecting a group loads field-level detail.
5. Edits are keyed by stable `field_id`, not display labels.
6. `buildReviewPatchOperations()` maps editable field IDs to backend card fields.
7. Each operation calls `patchEvidence(canonicalEvidenceId, body)`.
8. Backend `FeedbackService` updates `CanonicalEvidenceItem`, records `ReviewAuditEvent`, and refreshes derived profile/search views.
9. Frontend invalidates `["audit", "events"]`, so the new event appears in the audit table.

## Testing

```bash
cd frontend
bun run test tests/audit/reviewPatch.test.tsx tests/audit/useAuditEvents.test.tsx
```

## Dependencies

| Dependency | Purpose |
| --- | --- |
| `antd` | Drawer, Table, Input, Button, Segmented, Tag, Typography, Select |
| `@tanstack/react-query` | Audit event fetching, polling, cache invalidation |
| `axios` via `apiClient` | HTTP transport for Phase 4 APIs |
| `lucide-react` | Icons (Search, ArrowRight, ClipboardCheck, ArrowLeft, CheckCircle2, X) |
| Local UI primitives | `Badge`, `MetricTile`, formatting utilities |
