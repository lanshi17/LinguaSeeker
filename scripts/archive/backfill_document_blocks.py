"""Backfill original_blocks / translated_blocks for existing source documents.

For each source document that has NULL original_blocks (or translated_blocks),
this script tries in order:
  1. Load structured blocks from pipeline / cross_lingual output JSON (has bbox).
  2. Parse blocks from the stored document text via markdown-to-blocks (no bbox).

Usage:
    cd backend
    uv run python ../scripts/data/import/backfill_document_blocks.py
    uv run python ../scripts/data/import/backfill_document_blocks.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

# ── Environment selection (must happen before config import) ─────────────────


def _parse_env_from_argv() -> str:
    for arg in sys.argv[1:]:
        if arg.startswith("--environment="):
            return arg.split("=", 1)[1]
    return "development"


os.environ["ENVIRONMENT"] = _parse_env_from_argv()

from loguru import logger  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select, update  # noqa: E402

from src.core.config import get_config  # noqa: E402
from src.dao.postgresql.connection import (  # noqa: E402
    async_session_factory,
    build_async_engine,
)
from src.dao.postgresql.models import SourceDocument, SourceDocumentIdentifier  # noqa: E402


# ── Block loading from disk ──────────────────────────────────────────────────


def _load_blocks_from_dir(doc_dir: Path, track: str) -> list[dict] | None:
    """Load structured blocks from a {track}.json file."""
    doc_file = doc_dir / f"{track}.json"
    if not doc_file.exists():
        return None
    try:
        with open(doc_file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    blocks = data.get("blocks")
    if isinstance(blocks, list) and blocks:
        return blocks
    return None


def _load_blocks_from_disk(
    source_document_id: str,
    track: str,
    identifiers: dict[str, str] | None = None,
) -> list[dict] | None:
    """Search pipeline output and cross_lingual dirs for structured blocks."""
    backend_root = BACKEND_ROOT
    doc_id_str = str(source_document_id)

    # 1. Pipeline output: backend/data/pipeline/{run_id}/phase_2/{doc_id}/
    pipeline_root = backend_root / "data" / "pipeline"
    if pipeline_root.exists():
        for pipeline_dir in pipeline_root.iterdir():
            if not pipeline_dir.is_dir():
                continue
            doc_dir = pipeline_dir / "phase_2" / doc_id_str
            result = _load_blocks_from_dir(doc_dir, track)
            if result:
                return result

    # 2. Legacy output: backend/output/cross_lingual/{lang}/{doc_id}/
    legacy_root = backend_root / "output" / "cross_lingual"
    if legacy_root.exists():
        for lang_dir in legacy_root.iterdir():
            if not lang_dir.is_dir():
                continue
            result = _load_blocks_from_dir(lang_dir / doc_id_str, track)
            if result:
                return result

        # 3. Search by identifiers (DOI/PMID → dir name with / replaced by _)
        if identifiers:
            search_keys = [
                v.replace("/", "_")
                for v in identifiers.values()
                if v
            ]
            for lang_dir in legacy_root.iterdir():
                if not lang_dir.is_dir():
                    continue
                for child in lang_dir.iterdir():
                    if not child.is_dir():
                        continue
                    if child.name in search_keys or child.name.replace("/", "_") in search_keys:
                        result = _load_blocks_from_dir(child, track)
                        if result:
                            return result

    return None


# ── Markdown-to-blocks parser ────────────────────────────────────────────────


def _markdown_to_blocks(markdown: str) -> list[dict] | None:
    """Parse a markdown document into MinerU-style ContentBlock dicts."""
    if not markdown or not markdown.strip():
        return None
    blocks: list[dict] = []
    lines = markdown.split("\n")
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        # Heading
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            blocks.append({
                "type": "title",
                "text_level": len(heading.group(1)),
                "text": heading.group(2).strip(),
                "page_idx": 0,
            })
            i += 1
            continue
        # Image
        image = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", stripped)
        if image:
            blocks.append({
                "type": "image",
                "img_path": image.group(2).strip(),
                "image_caption": [image.group(1)] if image.group(1) else [],
                "page_idx": 0,
            })
            i += 1
            continue
        # HTML table
        if stripped.lower().startswith("<table"):
            table_lines = [line]
            i += 1
            while i < n and "</table>" not in lines[i].lower():
                table_lines.append(lines[i])
                i += 1
            if i < n:
                table_lines.append(lines[i])
                i += 1
            blocks.append({
                "type": "table",
                "table_body": "\n".join(table_lines),
                "text": "",
                "page_idx": 0,
            })
            continue
        # Markdown table
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1].strip()):
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            header_cells = [c.strip() for c in table_lines[0].strip("|").split("|")]
            rows = [[c.strip() for c in tl.strip("|").split("|")] for tl in table_lines[2:]]
            html = '<table><thead><tr>' + "".join(f"<th>{c}</th>" for c in header_cells) + "</tr></thead><tbody>"
            for row in rows:
                html += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            html += "</tbody></table>"
            blocks.append({
                "type": "table",
                "table_body": html,
                "text": "",
                "page_idx": 0,
            })
            continue
        # List items
        if re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            items: list[str] = []
            while i < n and (re.match(r"^[-*]\s+", lines[i].strip()) or re.match(r"^\d+\.\s+", lines[i].strip())):
                items.append(re.sub(r"^[-*]\s+|^\d+\.\s+", "", lines[i].strip()))
                i += 1
            blocks.append({
                "type": "list",
                "list_items": items,
                "text": "\n".join(items),
                "page_idx": 0,
            })
            continue
        # Blank line
        if not stripped:
            i += 1
            continue
        # Text paragraph
        para_lines = [line]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if not nxt or re.match(r"^#{1,6}\s+", nxt) or re.match(r"^!\[", nxt):
                break
            if nxt.lower().startswith("<table"):
                break
            if nxt.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1].strip()):
                break
            if re.match(r"^[-*]\s+", nxt) or re.match(r"^\d+\.\s+", nxt):
                break
            para_lines.append(lines[i])
            i += 1
        blocks.append({
            "type": "text",
            "text": "\n".join(para_lines).strip(),
            "page_idx": 0,
        })
    return blocks if blocks else None


# ── Backfill logic ───────────────────────────────────────────────────────────


async def backfill(dry_run: bool = False) -> None:
    cfg = get_config()
    engine = build_async_engine(cfg)
    factory = async_session_factory(engine)

    async with factory() as session:
        # Find all docs with NULL original_blocks
        stmt = select(
            SourceDocument.source_document_id,
            SourceDocument.original_text,
            SourceDocument.translated_text,
            SourceDocument.original_blocks,
            SourceDocument.translated_blocks,
        ).where(
            (SourceDocument.original_blocks.is_(None))
            | (SourceDocument.translated_blocks.is_(None)),
        )
        result = await session.execute(stmt)
        rows = result.all()

        logger.info("Found {} documents with missing blocks", len(rows))

        backfilled = 0
        skipped = 0

        for row in rows:
            doc_id = row[0]
            orig_text = row[1]
            trans_text = row[2]
            existing_orig_blocks = row[3]
            existing_trans_blocks = row[4]

            # Load identifiers for disk-based block search
            ident_stmt = select(
                SourceDocumentIdentifier.identifier_type,
                SourceDocumentIdentifier.identifier_value,
            ).where(SourceDocumentIdentifier.source_document_id == doc_id)
            ident_result = await session.execute(ident_stmt)
            identifiers = {
                r[0]: r[1] for r in ident_result.all() if r[0] and r[1]
            }

            doc_id_str = str(doc_id)
            update_fields: dict = {}

            # Original blocks
            if existing_orig_blocks is None:
                orig_blocks = (
                    _load_blocks_from_disk(doc_id_str, "original", identifiers)
                    or _markdown_to_blocks(orig_text or "")
                )
                if orig_blocks:
                    update_fields["original_blocks"] = orig_blocks

            # Translated blocks
            if existing_trans_blocks is None:
                trans_blocks = (
                    _load_blocks_from_disk(doc_id_str, "translated", identifiers)
                    or _markdown_to_blocks(trans_text or "")
                )
                if trans_blocks:
                    update_fields["translated_blocks"] = trans_blocks

            if not update_fields:
                skipped += 1
                continue

            if dry_run:
                logger.info(
                    "[DRY-RUN] Would update {}: orig_blocks={}, trans_blocks={}",
                    doc_id_str[:8],
                    "original_blocks" in update_fields,
                    "translated_blocks" in update_fields,
                )
            else:
                await session.execute(
                    update(SourceDocument)
                    .where(SourceDocument.source_document_id == doc_id)
                    .values(**update_fields),
                )
                logger.info(
                    "Updated {}: orig_blocks={}, trans_blocks={}",
                    doc_id_str[:8],
                    "original_blocks" in update_fields,
                    "translated_blocks" in update_fields,
                )
            backfilled += 1

        if not dry_run and backfilled > 0:
            await session.commit()

        logger.info(
            "Done: {} documents backfilled, {} skipped (no text or already had blocks)",
            backfilled,
            skipped,
        )

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill document blocks")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing to DB",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    asyncio.run(backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
