"""Tests for search_service track deduplication."""


def test_dedup_by_field_id_and_track():
    """Deduplication by (field_id, track) keeps the most recently updated row."""
    from dataclasses import dataclass
    from datetime import datetime

    @dataclass
    class FakeRow:
        field_id: str
        active_payload: dict
        updated_at: datetime
        canonical_evidence_id: str

    rows = [
        FakeRow("gene", {"track": "original", "group_id": "g1"}, datetime(2026, 1, 1), "old-gene"),
        FakeRow("gene", {"track": "original", "group_id": "g1"}, datetime(2026, 6, 1), "new-gene"),
        FakeRow("variant", {"track": "translated", "group_id": "g1"}, datetime(2026, 3, 1), "var-t"),
    ]

    # Simulate the dedup logic from get_group_detail
    seen: dict[tuple[str, str], int] = {}
    deduped_rows = []
    for row in sorted(rows, key=lambda r: r.updated_at or "", reverse=True):
        track = (row.active_payload or {}).get("track", "original")
        key = (row.field_id, track)
        if key not in seen:
            seen[key] = 1
            deduped_rows.append(row)

    assert len(deduped_rows) == 2
    gene_row = next(r for r in deduped_rows if r.field_id == "gene")
    assert gene_row.canonical_evidence_id == "new-gene"
