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

## Architecture

```text
AuditPage
  -> AuditView
      -> useAuditEvents()
          -> GET /api/v1/delta-audit/
      -> AuditEventTable
      -> AuditEventDetailDrawer
      -> EvidenceReviewDrawer
          -> searchEvidence()
          -> getEvidenceGroupDetail()
          -> buildReviewPatchOperations()
          -> PATCH /api/v1/evidence/{canonical_evidence_id}
          -> invalidate ["audit", "events"]
```

The backend Phase 4 API is authoritative for persistence. The frontend only builds typed request payloads, renders returned deltas, and keeps React Query caches scoped to the same filters sent to the API.

## Public API

### `AuditView`

| Export | Signature | Description |
| --- | --- | --- |
| `AuditView` | `function AuditView(): JSX.Element` | Page-level orchestrator for audit metrics, filters, table, detail drawer, and evidence review drawer. |

### `AuditEventTable`

| Export | Signature | Description |
| --- | --- | --- |
| `AuditEventTable` | `function AuditEventTable({ events, loading, onRowClick }: AuditEventTableProps): JSX.Element` | Displays audit events with status transitions, field-change counts, reasons, and row click selection. |

### `AuditEventDetailDrawer`

| Export | Signature | Description |
| --- | --- | --- |
| `AuditEventDetailDrawer` | `function AuditEventDetailDrawer({ event, open, onClose }: AuditEventDetailDrawerProps): JSX.Element \| null` | Shows event metadata and field-level old/new values. |

### `EvidenceReviewDrawer`

| Export | Signature | Description |
| --- | --- | --- |
| `EvidenceReviewDrawer` | `function EvidenceReviewDrawer({ open, onClose }: EvidenceReviewDrawerProps): JSX.Element` | Searches evidence groups, lets reviewers edit mapped fields, submits status and value corrections, and refreshes audit events. |

### Hooks And Services

| Export | Signature | Description |
| --- | --- | --- |
| `useAuditEvents` | `function useAuditEvents(query: AuditEventQuery = {})` | React Query hook for audit event lists. Query key includes `canonical_evidence_id`, `source_document_id`, `reviewer_id`, and `limit`. |
| `listAuditEvents` | `async function listAuditEvents(query: AuditEventQuery = {}): Promise<ReviewAuditEventResponse[]>` | Calls `GET /api/v1/delta-audit/` with optional filters. |

### Patch Utilities

| Export | Signature | Description |
| --- | --- | --- |
| `cardFieldForFieldId` | `function cardFieldForFieldId(fieldId: string): string \| null` | Maps Phase 4 field IDs like `A.gene_symbol` to backend card fields like `gene`. |
| `buildReviewPatchOperations` | `function buildReviewPatchOperations(args: BuildReviewPatchOperationsArgs): ReviewPatchOperation[]` | Converts field-level group edits into `PATCH /evidence/{id}` operations. Unmapped fields become status-only updates. |

## Data Flow

1. `AuditView` loads audit events with `useAuditEvents({ limit: 500 })`.
2. Users filter by status or search local event fields.
3. `EvidenceReviewDrawer` searches evidence by gene, variant, or disease.
4. Selecting a group loads field-level detail.
5. Edits are keyed by stable `field_id`, not display labels.
6. `buildReviewPatchOperations()` maps editable field IDs to backend card fields.
7. Each operation calls `patchEvidence(canonicalEvidenceId, body)`.
8. Backend `FeedbackService` updates `CanonicalEvidenceItem`, records `ReviewAuditEvent`, and refreshes derived profile/search views.
9. Frontend invalidates `["audit", "events"]`, so the new event appears in the audit table.

## Field Mapping

The backend accepts only card-level patch fields. Do not send raw `field_id` or `field_name` as a PATCH key.

| Field ID | Card field |
| --- | --- |
| `A.gene_symbol` | `gene` |
| `B.disease_diagnosis` | `disease` |
| `B.clinical_diagnosis` | `disease` |
| `J.authority_classification` | `classification` |
| `A.variant_hgvs_*` | `variant` |
| `A.variant_legacy_name` | `variant` |

Unmapped fields can still be approved, corrected, or rejected as status-only reviews. Their value input is disabled in `EvidenceReviewDrawer`.

## Extension Guide

When adding a new editable evidence field:

1. Add the backend card field to `EvidenceCardPayload.DIFF_FIELDS` and `EvidencePatchRequest` validation if it is not already supported.
2. Add the field-id mapping to `cardFieldForFieldId()`.
3. Add a `buildReviewPatchOperations()` test showing the exact PATCH body.
4. Verify API behavior with a Phase 4 test that writes an audit event and reads it through `/api/v1/delta-audit/`.

When adding a new audit filter:

1. Add it to `AuditEventQuery`.
2. Add it to `listAuditEvents()` params.
3. Add it to the `useAuditEvents()` query key.
4. Add a hook or service test that proves different filter values do not share cached results.

## Dependencies

| Dependency | Purpose |
| --- | --- |
| `antd` | Drawer, table, inputs, buttons, segmented controls, tags, typography. |
| `@tanstack/react-query` | Audit event fetching, polling, cache invalidation. |
| `axios` via `apiClient` | HTTP transport for Phase 4 APIs. |
| `lucide-react` | Button and table icons. |
| Local UI primitives | `Badge`, `MetricTile`, and formatting utilities. |

## Testing

```bash
cd frontend
bun run test tests/audit/reviewPatch.test.tsx tests/audit/useAuditEvents.test.tsx
bun run type-check
```

Backend API coverage for this flow:

```bash
cd backend
uv run pytest tests/api/test_delta_audit_api.py tests/api/test_evidence_api.py
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_delta_audit.py tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py
```

The API-level audit test proves this critical path:

```text
PATCH /api/v1/evidence/{canonical_evidence_id}
  -> FeedbackService.patch_evidence()
  -> ReviewAuditEvent inserted
GET /api/v1/delta-audit/?source_document_id=...
  -> event returned with field_deltas and status transition
```
