#!/usr/bin/env python3
"""Export pipeline-generated business data from the dev PostgreSQL database.

Scope: literature + parsing artifacts only.
Filter: one processing_run per source_document (latest completed run).
Output: a single SQL file using COPY ... FROM STDIN, safe for psql import.

Usage:
    uv run python scripts/data/export/export_pipeline_business_data.py \
        --out lingua_seeker_pipeline_data.sql \
        --host localhost --port 5432 --dbname dev_lingua_seeker \
        --user lingua_seeker --password <pw> --schema lingua_seeker

All DB options fall back to standard PG* env vars, then to sensible defaults.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections.abc import Iterable
from datetime import datetime, timezone

import asyncpg


LITERATURE_TABLES: tuple[str, ...] = (
    "source_documents",
    "source_document_identifiers",
    "processing_runs",
    "run_evidence_items",
    "evidence_entity_bindings",
    "canonical_evidence_items",
    "normalized_entities",
    "literature_profiles",
    "document_annotations",
)

# Conflict target used by INSERT ... ON CONFLICT (...) DO NOTHING.
# Tables without an entry fall back to plain INSERT (no conflict handling).
CONFLICT_TARGET: dict[str, str] = {
    "source_documents": "(source_document_id)",
    "source_document_identifiers": "(identifier_type, identifier_value)",
    "processing_runs": "(processing_run_id)",
    "run_evidence_items": "(run_evidence_item_id)",
    "evidence_entity_bindings": "(evidence_entity_binding_id)",
    "canonical_evidence_items": "(canonical_evidence_id)",
    "normalized_entities": "(entity_id)",
    "literature_profiles": "(source_document_id)",
    "document_annotations": "(id)",
}

COPY_CHUNK_SIZE = 1000


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Output SQL file path.")
    parser.add_argument("--host", default=os.environ.get("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PGPORT", "5432")))
    parser.add_argument("--dbname", default=os.environ.get("PGDATABASE", "dev_lingua_seeker"))
    parser.add_argument("--user", default=os.environ.get("PGUSER", "lingua_seeker"))
    parser.add_argument("--password", default=os.environ.get("PGPASSWORD", ""))
    parser.add_argument("--schema", default=os.environ.get("PGSCHEMA", "lingua_seeker"))
    parser.add_argument(
        "--title-list",
        default=None,
        help=(
            "Optional JSON file with a list of titles (or {'titles':[...]}) to "
            "restrict the export to. Titles are normalized (lowercased, "
            "punctuation stripped) before matching."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("insert", "copy"),
        default="insert",
        help=(
            "Output format. 'insert' (default) emits INSERT ... ON CONFLICT "
            "DO NOTHING — robust against schema mismatches and duplicate rows, "
            "no superuser or TRUNCATE required. 'copy' emits COPY ... FROM "
            "stdin — faster but fragile (requires exact schema match and "
            "superuser for session_replication_role)."
        ),
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Print filter statistics and exit without writing the SQL file.",
    )
    return parser.parse_args()


def _sql_literal(value: object) -> str:
    """Format a Python value as a PostgreSQL SQL literal for INSERT."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    from decimal import Decimal
    if isinstance(value, Decimal):
        return str(value)
    text = str(value)
    # Dollar-quoting avoids escaping single quotes; safe as long as the
    # payload doesn't contain the $$ delimiter (not produced by json.dumps).
    return f"$${text}$$"


def _normalize_title(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[\s\-–—]+", " ", s)
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _load_title_filter(path: str) -> set[str]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    titles = data.get("titles") if isinstance(data, dict) else data
    if not isinstance(titles, list):
        raise ValueError(f"--title-list must contain a list, got {type(titles).__name__}")
    return {t for t in (_normalize_title(x) for x in titles) if t}


def _pg_copy_escape(value: object) -> str:
    if value is None:
        return "\\N"
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
    text = str(value)
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


async def _resolve_filter(
    conn: asyncpg.Connection,
    title_filter: set[str] | None,
) -> tuple[list[str], list[str], dict[str, object]]:
    """Return (doc_ids, run_ids, stats) for the export filter.

    Default: latest completed processing_run per source_document.
    With title_filter: for each normalized title in the filter, pick the
    source_document whose latest completed run is the most recent overall
    (collapses re-ingested duplicates of the same paper).
    """
    if title_filter is None:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (source_document_id)
                   source_document_id, processing_run_id, created_at
            FROM   processing_runs
            WHERE  run_status = 'completed'
            ORDER  BY source_document_id, created_at DESC, processing_run_id DESC
            """
        )
        doc_ids = [str(r["source_document_id"]) for r in rows]
        run_ids = [str(r["processing_run_id"]) for r in rows]
        total_docs = await conn.fetchval("SELECT COUNT(*) FROM source_documents")
        total_runs = await conn.fetchval("SELECT COUNT(*) FROM processing_runs WHERE run_status = 'completed'")
        stats = {
            "mode": "per_source_document",
            "total_source_documents": total_docs,
            "total_completed_runs": total_runs,
            "chosen_documents": len(doc_ids),
        }
        return doc_ids, run_ids, stats

    rows = await conn.fetch(
        "SELECT source_document_id, raw_metadata FROM source_documents"
    )
    title_to_doc: dict[str, list[str]] = {}
    for r in rows:
        meta = r["raw_metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        title = meta.get("title") if isinstance(meta, dict) else None
        nt = _normalize_title(title)
        if not nt or nt not in title_filter:
            continue
        title_to_doc.setdefault(nt, []).append(str(r["source_document_id"]))

    chosen_doc_ids: set[str] = set()
    chosen_run_ids: set[str] = set()
    matched_titles = 0
    skipped_titles = 0
    for nt, docs in title_to_doc.items():
        best = await conn.fetchrow(
            """
            SELECT source_document_id, processing_run_id
            FROM   processing_runs
            WHERE  source_document_id = ANY($1::uuid[])
              AND  run_status = 'completed'
            ORDER  BY created_at DESC, processing_run_id DESC
            LIMIT  1
            """,
            docs,
        )
        if best is None:
            skipped_titles += 1
            continue
        chosen_doc_ids.add(str(best["source_document_id"]))
        chosen_run_ids.add(str(best["processing_run_id"]))
        matched_titles += 1

    stats = {
        "mode": "per_benchmark_title",
        "filter_titles": len(title_filter),
        "matched_titles": matched_titles,
        "skipped_titles_no_completed_run": skipped_titles,
        "chosen_documents": len(chosen_doc_ids),
    }
    return sorted(chosen_doc_ids), sorted(chosen_run_ids), stats


async def _preview(conn: asyncpg.Connection, schema: str, title_filter: set[str] | None) -> None:
    doc_ids, run_ids, stats = await _resolve_filter(conn, title_filter)

    counts: list[tuple[str, int]] = []
    for table in LITERATURE_TABLES:
        if table == "source_documents":
            q = f"SELECT COUNT(*) FROM {schema}.{table} WHERE source_document_id = ANY($1::uuid[])"
            counts.append((table, await conn.fetchval(q, doc_ids)))
        elif table == "processing_runs":
            q = f"SELECT COUNT(*) FROM {schema}.{table} WHERE processing_run_id = ANY($1::uuid[])"
            counts.append((table, await conn.fetchval(q, run_ids)))
        elif table == "run_evidence_items":
            q = f"SELECT COUNT(*) FROM {schema}.{table} WHERE processing_run_id = ANY($1::uuid[])"
            counts.append((table, await conn.fetchval(q, run_ids)))
        elif table == "evidence_entity_bindings":
            q = (
                f"SELECT COUNT(*) FROM {schema}.{table} e "
                f"JOIN {schema}.run_evidence_items r ON r.run_evidence_item_id = e.run_evidence_item_id "
                f"WHERE r.processing_run_id = ANY($1::uuid[])"
            )
            counts.append((table, await conn.fetchval(q, run_ids)))
        elif table == "canonical_evidence_items":
            q = f"SELECT COUNT(*) FROM {schema}.{table} WHERE source_document_id = ANY($1::uuid[])"
            counts.append((table, await conn.fetchval(q, doc_ids)))
        elif table == "normalized_entities":
            q = (
                f"SELECT COUNT(DISTINCT e.entity_id) FROM {schema}.normalized_entities e "
                f"JOIN {schema}.evidence_entity_bindings b ON b.entity_id = e.entity_id "
                f"JOIN {schema}.run_evidence_items r ON r.run_evidence_item_id = b.run_evidence_item_id "
                f"WHERE r.processing_run_id = ANY($1::uuid[])"
            )
            counts.append((table, await conn.fetchval(q, run_ids)))
        elif table == "literature_profiles":
            q = f"SELECT COUNT(*) FROM {schema}.{table} WHERE source_document_id = ANY($1::uuid[])"
            counts.append((table, await conn.fetchval(q, doc_ids)))
        elif table == "source_document_identifiers":
            q = f"SELECT COUNT(*) FROM {schema}.{table} WHERE source_document_id = ANY($1::uuid[])"
            counts.append((table, await conn.fetchval(q, doc_ids)))
        elif table == "document_annotations":
            q = f"SELECT COUNT(*) FROM {schema}.{table} WHERE source_document_id = ANY($1::uuid[])"
            counts.append((table, await conn.fetchval(q, doc_ids)))

    total_runs = await conn.fetchval(f"SELECT COUNT(*) FROM {schema}.processing_runs")
    completed_runs = await conn.fetchval(
        f"SELECT COUNT(*) FROM {schema}.processing_runs WHERE run_status = 'completed'"
    )
    total_docs = await conn.fetchval(f"SELECT COUNT(*) FROM {schema}.source_documents")

    print(f"Schema: {schema}")
    print(f"Total source_documents:        {total_docs}")
    print(f"Total processing_runs:         {total_runs}")
    print(f"Completed processing_runs:     {completed_runs}")
    for k, v in stats.items():
        print(f"Filter.{k}: {v}")
    print()
    print("Rows that would be exported:")
    for table, count in counts:
        print(f"  {table:<30} {count}")


async def _fetch_column_names(conn: asyncpg.Connection, schema: str, table: str) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM   information_schema.columns
        WHERE  table_schema = $1 AND table_name = $2
        ORDER  BY ordinal_position
        """,
        schema,
        table,
    )
    return [r["column_name"] for r in rows]


async def _dump_table(
    conn: asyncpg.Connection,
    schema: str,
    table: str,
    query: str,
    params: Iterable[object],
    out: io.TextIOBase,
    mode: str,
) -> int:
    columns = await _fetch_column_names(conn, schema, table)
    rows = await conn.fetch(query, *params)

    if mode == "copy":
        out.write(f"COPY {schema}.{table} ({', '.join(columns)}) FROM stdin;\n")
        for record in rows:
            values = [_pg_copy_escape(record[c]) for c in columns]
            out.write("\t".join(values) + "\n")
        out.write("\\.\n\n")
        return len(rows)

    # INSERT ... ON CONFLICT DO NOTHING
    col_list = ", ".join(columns)
    conflict = CONFLICT_TARGET.get(table)
    suffix = f" ON CONFLICT {conflict} DO NOTHING" if conflict else ""
    for record in rows:
        values = [_sql_literal(record[c]) for c in columns]
        out.write(f"INSERT INTO {schema}.{table} ({col_list}) VALUES ({', '.join(values)}){suffix};\n")
    out.write("\n")
    return len(rows)


async def _export(args: argparse.Namespace, title_filter: set[str] | None) -> None:
    conn = await asyncpg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.dbname,
    )
    try:
        doc_ids, run_ids, stats = await _resolve_filter(conn, title_filter)
        if not doc_ids:
            print("No completed processing_runs found; nothing to export.", file=sys.stderr)
            return

        schema = args.schema

        print(f"Filter stats:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        print(f"Writing to {args.out} ...")

        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(f"-- Lingua Seeker pipeline business data export\n")
            fh.write(f"-- Generated: {datetime.now(timezone.utc).isoformat()}\n")
            fh.write(f"-- Source DB: {args.dbname}  Schema: {schema}\n")
            fh.write(f"-- Filter mode: {stats.get('mode')}\n")
            fh.write(f"-- Documents: {len(doc_ids)}   Runs: {len(run_ids)}\n")
            if args.mode == "copy":
                fh.write("SET session_replication_role = 'replica';\n\n")
            else:
                fh.write("BEGIN;\n\n")

            counts: dict[str, int] = {}

            counts["source_documents"] = await _dump_table(
                conn, schema, "source_documents",
                f"SELECT * FROM {schema}.source_documents WHERE source_document_id = ANY($1::uuid[])",
                [doc_ids], fh, args.mode,
            )
            counts["source_document_identifiers"] = await _dump_table(
                conn, schema, "source_document_identifiers",
                f"SELECT * FROM {schema}.source_document_identifiers WHERE source_document_id = ANY($1::uuid[])",
                [doc_ids], fh, args.mode,
            )
            counts["processing_runs"] = await _dump_table(
                conn, schema, "processing_runs",
                f"SELECT * FROM {schema}.processing_runs WHERE processing_run_id = ANY($1::uuid[])",
                [run_ids], fh, args.mode,
            )
            counts["run_evidence_items"] = await _dump_table(
                conn, schema, "run_evidence_items",
                f"SELECT * FROM {schema}.run_evidence_items WHERE processing_run_id = ANY($1::uuid[])",
                [run_ids], fh, args.mode,
            )
            counts["evidence_entity_bindings"] = await _dump_table(
                conn, schema, "evidence_entity_bindings",
                (
                    f"SELECT e.* FROM {schema}.evidence_entity_bindings e "
                    f"JOIN {schema}.run_evidence_items r ON r.run_evidence_item_id = e.run_evidence_item_id "
                    f"WHERE r.processing_run_id = ANY($1::uuid[])"
                ),
                [run_ids], fh, args.mode,
            )
            counts["normalized_entities"] = await _dump_table(
                conn, schema, "normalized_entities",
                (
                    f"SELECT DISTINCT e.* FROM {schema}.normalized_entities e "
                    f"JOIN {schema}.evidence_entity_bindings b ON b.entity_id = e.entity_id "
                    f"JOIN {schema}.run_evidence_items r ON r.run_evidence_item_id = b.run_evidence_item_id "
                    f"WHERE r.processing_run_id = ANY($1::uuid[])"
                ),
                [run_ids], fh, args.mode,
            )
            counts["canonical_evidence_items"] = await _dump_table(
                conn, schema, "canonical_evidence_items",
                f"SELECT * FROM {schema}.canonical_evidence_items WHERE source_document_id = ANY($1::uuid[])",
                [doc_ids], fh, args.mode,
            )
            counts["literature_profiles"] = await _dump_table(
                conn, schema, "literature_profiles",
                f"SELECT * FROM {schema}.literature_profiles WHERE source_document_id = ANY($1::uuid[])",
                [doc_ids], fh, args.mode,
            )
            counts["document_annotations"] = await _dump_table(
                conn, schema, "document_annotations",
                f"SELECT * FROM {schema}.document_annotations WHERE source_document_id = ANY($1::uuid[])",
                [doc_ids], fh, args.mode,
            )

            if args.mode == "copy":
                fh.write("SET session_replication_role = 'origin';\n")
            else:
                fh.write("COMMIT;\n")

        print("Export complete. Row counts:")
        for table, count in counts.items():
            print(f"  {table:<30} {count}")
        print()
        print("Import on production (after clearing target tables if needed):")
        print(f"  psql -h <host> -U lingua_seeker -d lingua_seeker -f {args.out}")
    finally:
        await conn.close()


async def main() -> None:
    args = _parse_args()
    title_filter: set[str] | None = (
        _load_title_filter(args.title_list) if args.title_list else None
    )
    if title_filter is not None:
        print(f"Loaded {len(title_filter)} normalized benchmark titles from {args.title_list}")

    conn = await asyncpg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.dbname,
    )
    try:
        if args.preview:
            await _preview(conn, args.schema, title_filter)
            return
    finally:
        await conn.close()

    await _export(args, title_filter)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
