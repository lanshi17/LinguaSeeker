"""Inventory reusable ClinGen pipeline runs in PostgreSQL."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Sequence

import yaml
from sqlalchemy import text

from benchmark.core import GROUND_TRUTH_DIR
from src.dao.postgresql.connection import async_session_factory, build_async_engine


_SUCCESS_STATUSES = {"completed"}


@dataclass(frozen=True)
class SystemRunRow:
    """One persisted pipeline run row relevant to ClinGen inventory."""

    processing_run_id: str
    source_document_id: str
    pipeline_status: str
    source_key: str | None
    evidence_count: int
    found_count: int
    source_span_count: int
    updated_at: str


@dataclass(frozen=True)
class SystemRunInventory:
    """Coverage summary for reusable ClinGen system runs."""

    total_expected: int
    best_by_entry: dict[str, SystemRunRow]
    missing_entry_ids: list[str]
    unmapped_count: int

    @property
    def mapped_count(self) -> int:
        """Number of expected ClinGen entries with at least one reusable run."""
        return len(self.best_by_entry)


def parse_entry_id(
    source_key: str | None,
    *,
    entry_id_key: str = "clingen",
    entry_id_pattern: str = r"\b(clingen_\d+)\b",
) -> str | None:
    """Extract a benchmark entry ID from a durable pipeline source key."""
    if not source_key:
        return None
    explicit_match = re.search(
        rf"(?:^|\|){re.escape(entry_id_key)}=([^|]+)(?:\||$)",
        source_key,
    )
    if explicit_match:
        return explicit_match.group(1)
    filename_match = re.search(entry_id_pattern, source_key)
    return filename_match.group(1) if filename_match else None


def parse_clingen_entry_id(source_key: str | None) -> str | None:
    """Extract a ClinGen benchmark entry ID from a durable pipeline source key."""
    return parse_entry_id(source_key)


def choose_best_run(rows: Sequence[SystemRunRow]) -> SystemRunRow:
    """Choose the most reusable run for one ClinGen entry."""
    return max(
        rows,
        key=lambda row: (
            row.pipeline_status in _SUCCESS_STATUSES,
            row.source_span_count,
            row.evidence_count,
            row.found_count,
            row.updated_at,
        ),
    )


def is_reconstructable_run(row: SystemRunRow) -> bool:
    """Return whether a DB run can safely rebuild a grounded Phase 2 artifact."""
    return (
        row.pipeline_status in _SUCCESS_STATUSES
        and row.evidence_count > 0
        and row.source_span_count > 0
    )


def build_inventory(
    rows: Sequence[SystemRunRow],
    expected_entry_ids: Sequence[str],
    *,
    entry_id_key: str = "clingen",
    entry_id_pattern: str = r"\b(clingen_\d+)\b",
) -> SystemRunInventory:
    """Build coverage inventory from persisted run rows and expected entries."""
    expected = list(expected_entry_ids)
    expected_set = set(expected)
    by_entry: dict[str, list[SystemRunRow]] = {}
    unmapped_count = 0
    for row in rows:
        entry_id = parse_entry_id(
            row.source_key,
            entry_id_key=entry_id_key,
            entry_id_pattern=entry_id_pattern,
        )
        if not entry_id:
            unmapped_count += 1
            continue
        if entry_id not in expected_set:
            unmapped_count += 1
            continue
        by_entry.setdefault(entry_id, []).append(row)

    best_by_entry = {
        entry_id: choose_best_run(entry_rows)
        for entry_id, entry_rows in sorted(by_entry.items())
    }
    missing_entry_ids = [entry_id for entry_id in expected if entry_id not in best_by_entry]
    return SystemRunInventory(
        total_expected=len(expected),
        best_by_entry=best_by_entry,
        missing_entry_ids=missing_entry_ids,
        unmapped_count=unmapped_count,
    )


def format_inventory(inventory: SystemRunInventory) -> str:
    """Format an inventory for terminal output and progress records."""
    missing = ",".join(inventory.missing_entry_ids) if inventory.missing_entry_ids else "none"
    lines = [
        (
            f"mapped={inventory.mapped_count}/{inventory.total_expected} "
            f"unmapped_rows={inventory.unmapped_count} missing={missing}"
        ),
        "entry run status evidence found spans source_key",
    ]
    for entry_id, row in sorted(inventory.best_by_entry.items()):
        lines.append(
            f"{entry_id} {row.processing_run_id} {row.pipeline_status} "
            f"evidence={row.evidence_count} found={row.found_count} spans={row.source_span_count} "
            f"{row.source_key or ''}"
        )
    return "\n".join(lines)


def load_expected_entry_ids(ground_truth_dir: Path = GROUND_TRUTH_DIR) -> list[str]:
    """Load expected ClinGen entry IDs from the benchmark selection file."""
    import json

    selection_path = ground_truth_dir / "selection.json"
    entries = json.loads(selection_path.read_text(encoding="utf-8"))
    return [
        str(entry["entry_id"])
        for entry in entries
        if (ground_truth_dir / str(entry["entry_id"]) / "source.md").exists()
    ]


def load_postgres_env_from_vault(vault_path: Path | None) -> None:
    """Load non-printed PostgreSQL credentials from a local vault file."""
    if vault_path is None or not vault_path.exists():
        return
    data = yaml.safe_load(vault_path.read_text(encoding="utf-8")) or {}
    postgres = data.get("postgres") or {}
    if postgres.get("user"):
        os.environ["POSTGRES_USER"] = str(postgres["user"])
    if postgres.get("password"):
        os.environ["POSTGRES_PASSWORD"] = str(postgres["password"])


async def query_system_run_rows() -> list[SystemRunRow]:
    """Query persisted pipeline states with evidence counts."""
    engine = build_async_engine()
    session_factory = async_session_factory(engine)
    try:
        async with session_factory() as session:
            rows = (
                await session.execute(text(
                    """
                    select prs.processing_run_id::text,
                           prs.source_document_id::text,
                           prs.pipeline_status,
                           prs.source_key,
                           prs.updated_at::text,
                           count(rei.run_evidence_item_id) as evidence_count,
                           count(*) filter (where rei.status = 'found') as found_count,
                           count(*) filter (where rei.source_span <> '{}'::jsonb) as source_span_count
                    from pipeline_run_states prs
                    left join run_evidence_items rei on rei.processing_run_id = prs.processing_run_id
                    group by prs.processing_run_id,
                             prs.source_document_id,
                             prs.pipeline_status,
                             prs.source_key,
                             prs.updated_at
                    order by prs.updated_at asc
                    """
                ))
            ).all()
    finally:
        await engine.dispose()

    return [
        SystemRunRow(
            processing_run_id=row.processing_run_id,
            source_document_id=row.source_document_id,
            pipeline_status=row.pipeline_status,
            source_key=row.source_key,
            evidence_count=int(row.evidence_count),
            found_count=int(row.found_count),
            source_span_count=int(row.source_span_count),
            updated_at=row.updated_at,
        )
        for row in rows
    ]


async def run_inventory(vault_path: Path | None = None) -> SystemRunInventory:
    """Query PostgreSQL and return reusable ClinGen run coverage."""
    load_postgres_env_from_vault(vault_path)
    rows = await query_system_run_rows()
    return build_inventory(rows, load_expected_entry_ids())


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help="Optional backend/config/vault/development.yaml path for local PostgreSQL credentials.",
    )
    args = parser.parse_args()
    inventory = asyncio.run(run_inventory(args.vault))
    print(format_inventory(inventory))


if __name__ == "__main__":
    main()
