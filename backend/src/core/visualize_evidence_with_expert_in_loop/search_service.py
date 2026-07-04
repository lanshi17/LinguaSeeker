"""Evidence search service with field-level pivoting."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger

from sqlalchemy import and_, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.parsing import parse_gene_from_group_id, parse_variant_from_group_id
from src.utils.text_normalize import block_text_from_dict, concat_document_text

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    TranslationAlignmentChunk,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.language_detector import detect_language
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceChainHighlight,
    EvidenceFieldDistribution,
    EvidenceGroupDetailResponse,
    EvidenceGroupItem,
    EvidenceSearchResponse,
    EvidenceSearchResult,
    EvidenceTrackTrace,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    PipelineRunState,
    SourceDocument,
    SourceDocumentIdentifier,
)

# Field ID prefixes that map to summary columns
_GENE_FIELDS = ("A.gene_symbol", "A.gene_aliases")
_VARIANT_FIELDS = (
    "A.variant_hgvs_c",
    "A.variant_hgvs_p",
    "A.variant_hgvs_g",
    "A.variant_legacy_name",
)
_DISEASE_FIELDS = ("B.disease_diagnosis", "B.clinical_diagnosis", "B.hpo_terms")
_CLASSIFICATION_FIELDS = ("J.authority_classification", "J.clinvar_assertion")
_TOKEN_BOUNDARY_CHARS = r"A-Za-z0-9_"
_BODY_START_PATTERNS = (
    r"^［?摘要］?",
    r"^摘\s*要\b",
    r"^abstract\b",
    r"^资料与方法\b",
    r"^\d+(?:\.\d+)?\s*[　 ]*(?:资料与方法|材料与方法|方法|研究对象|结果|讨论)\b",
    r"^methods?\b",
    r"^results?\b",
    r"^discussion\b",
    r"^introduction\b",
)
_BODY_END_PATTERNS = (
    r"^［?\s*参\s*考\s*文\s*献\s*］?",
    r"^参考文献\b",
    r"^references?\b",
    r"^acknowledg(?:e)?ments?\b",
    r"^conflicts?\s+of\s+interest\b",
    r"^funding\b",
    r"^（?本文编辑",
)
_BLOCK_TEXT_COVERAGE_RATIO = 0.7


def _coerce_str(value: Any) -> str | None:
    """Convert a payload value to a display string."""
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _normalize_language_code(value: Any) -> str | None:
    """Normalize a language value to the short code used by Evidence DB filters."""
    language_aliases = {
        "chinese": "zh",
        "deu": "de",
        "eng": "en",
        "english": "en",
        "fra": "fr",
        "fre": "fr",
        "french": "fr",
        "german": "de",
        "japanese": "ja",
        "jpn": "ja",
        "rus": "ru",
        "russian": "ru",
        "zho": "zh",
        "zh-cn": "zh",
        "zh-tw": "zh",
    }
    text = _coerce_str(value)
    if not text or not text.strip():
        return None
    normalized = text.strip().lower().replace("_", "-")
    if normalized == "unknown":
        return None
    return language_aliases.get(normalized, normalized)


def _extract_source_language(raw_metadata: Any) -> str | None:
    """Return the persisted source-language code from document metadata."""
    if not isinstance(raw_metadata, dict):
        return None
    for key in ("source_language", "article_language", "language"):
        language = _normalize_language_code(raw_metadata.get(key))
        if language:
            return language
    return None


def _extract_source_language_from_state(state_json: Any) -> str | None:
    """Return source language from persisted pipeline state JSON."""
    if not isinstance(state_json, dict):
        return None
    candidate_paths = (
        ("phase_2_output", "source_language"),
        ("phase_2_status", "summary", "source_language"),
        ("source_language",),
    )
    for path in candidate_paths:
        value: Any = state_json
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        language = _normalize_language_code(value)
        if language:
            return language
    return None


def _detect_source_language_from_text(text: str | None) -> str | None:
    """Infer source language from persisted original document text as a fallback."""
    if not text or not text.strip():
        return None
    language = _normalize_language_code(detect_language(text))
    if language:
        return language
    return None


def _matches_any(patterns: tuple[str, ...], text: str) -> bool:
    """Return whether stripped text matches any compiled body-boundary pattern."""
    stripped = text.strip()
    return any(re.search(pattern, stripped, re.IGNORECASE) for pattern in patterns)


def _compact_len(text: str | None) -> int:
    """Return length after whitespace compaction for coarse coverage checks."""
    if not text:
        return 0
    return len(re.sub(r"\s+", "", text))


def _filter_body_text(text: str | None) -> str | None:
    """Remove article metadata and trailing non-body sections from display text."""
    if not text or not text.strip():
        return None

    lines = text.splitlines()
    start = 0
    for index, line in enumerate(lines):
        if _matches_any(_BODY_START_PATTERNS, line):
            start = index
            break

    end = len(lines)
    for index in range(start, len(lines)):
        if _matches_any(_BODY_END_PATTERNS, lines[index]):
            end = index
            break

    filtered = "\n".join(lines[start:end]).strip()
    return filtered or text.strip()


def _filter_body_blocks(blocks: list[dict] | None, text: str | None = None) -> list[dict] | None:
    """Return body-only blocks, rebuilding from fuller text when stored blocks are truncated."""
    body_text = _filter_body_text(text)
    body_text_len = _compact_len(body_text)
    blocks_text = "\n\n".join(
        block_text_from_dict(block) for block in blocks or [] if isinstance(block, dict) and block_text_from_dict(block)
    )

    if body_text and (not blocks or _compact_len(blocks_text) < int(body_text_len * _BLOCK_TEXT_COVERAGE_RATIO)):
        return _markdown_to_blocks(body_text)
    if not blocks:
        return None

    start = 0
    for index, block in enumerate(blocks):
        if isinstance(block, dict) and _matches_any(_BODY_START_PATTERNS, block_text_from_dict(block)):
            start = index
            break

    end = len(blocks)
    for index in range(start, len(blocks)):
        block = blocks[index]
        if isinstance(block, dict) and _matches_any(_BODY_END_PATTERNS, block_text_from_dict(block)):
            end = index
            break

    filtered_blocks = [block for block in blocks[start:end] if isinstance(block, dict)]
    return filtered_blocks or None


def _category_from_field_id(field_id: str) -> str | None:
    """Infer the evidence category prefix from a field id."""
    if not field_id:
        return None
    if "." not in field_id:
        return field_id
    return field_id.split(".", 1)[0]


def _extract_summary_field(
    field_id: str,
    value: str | None,
    target: dict[str, str | None],
) -> None:
    """Extract gene/variant/disease/classification into target dict if not already set."""
    if field_id in _GENE_FIELDS and not target.get("gene"):
        target["gene"] = _coerce_str(value)
    elif field_id in _VARIANT_FIELDS and not target.get("variant"):
        target["variant"] = _coerce_str(value)
    elif field_id in _DISEASE_FIELDS and not target.get("disease"):
        target["disease"] = _coerce_str(value)
    elif field_id in _CLASSIFICATION_FIELDS and not target.get("classification"):
        target["classification"] = _coerce_str(value)


def _parse_source_offset(raw: object, *, default: int, name: str) -> tuple[int, bool]:
    """Parse a stored source offset, with default + validity flag for fallback.

    Returns (offset, valid). ``valid`` is False when the stored value was
    missing or malformed; callers use that to decide between clamping and
    value-anchor fallback.
    """
    if raw is None:
        return default, False
    try:
        return int(raw), True
    except (TypeError, ValueError):
        logger.warning(
            "Invalid source_span {}_offset={!r}; using value fallback",
            name,
            raw,
        )
        return default, False


def _find_value_anchor(text: str, value: str | None) -> tuple[int, int] | None:
    """Find a safe case-insensitive value anchor in snippet text.

    Single-letter values are too ambiguous in prose. Two-letter values are
    only matched when uppercase (typical for gene symbols like ``BR``).
    Three-or-more-letter values use a token-boundary regex with
    case-insensitive matching to avoid matching inside longer words.
    """
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if len(candidate) == 1:
        return None
    if len(candidate) == 2:
        if not candidate.isupper():
            return None
        match = re.search(
            rf"(?<![{_TOKEN_BOUNDARY_CHARS}]){re.escape(candidate)}(?![{_TOKEN_BOUNDARY_CHARS}])",
            text,
        )
        if not match:
            return None
        return match.start(), match.end()
    pattern = re.compile(
        rf"(?<![{_TOKEN_BOUNDARY_CHARS}]){re.escape(candidate)}(?![{_TOKEN_BOUNDARY_CHARS}])",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.start(), match.end()


def _build_highlight(
    source_span: dict[str, object],
    value: str | None = None,
) -> EvidenceChainHighlight | None:
    """Build a clamped highlight payload from a stored source span.

    Source spans store document-global offsets while text_snippet is a short
    excerpt. When offsets are malformed or start beyond the snippet, locate
    value inside the snippet using a safe token-boundary search. When the value
    cannot be located, start and end collapse to 0 (no visible highlight).
    """
    if not source_span or not isinstance(source_span, dict):
        return None

    text = str(source_span.get("text_snippet") or "")
    if not text:
        return None

    text_len = len(text)
    start, start_valid = _parse_source_offset(
        source_span.get("start_offset"),
        default=0,
        name="start",
    )
    end, end_valid = _parse_source_offset(
        source_span.get("end_offset"),
        default=text_len,
        name="end",
    )
    if end < start:
        end = text_len

    # Valid starts inside the snippet should keep current behavior: clamp the
    # end to snippet bounds instead of falling through to value search.
    if start_valid and end_valid and start < text_len:
        start = max(start, 0)
        end = min(max(end, start), text_len)
    else:
        anchor = _find_value_anchor(text, value)
        if anchor is None:
            start = end = 0
        else:
            start, end = anchor

    page = source_span.get("page")
    clean_source_span = {k: v for k, v in source_span.items() if v is not None}
    return EvidenceChainHighlight(
        text=text,
        highlight_start=max(start, 0),
        highlight_end=min(max(end, 0), text_len),
        page=page if isinstance(page, int) else None,
        source_span=clean_source_span,
    )


def _load_blocks_from_dir(doc_dir: Path, track: str) -> list[dict] | None:
    """Try to load structured blocks from a single document directory."""
    doc_file = doc_dir / f"{track}.json"
    if not doc_file.exists():
        return None
    try:
        with open(doc_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.warning("Failed to load {} blocks from {}", track, doc_file)
        return None
    if not isinstance(data, dict):
        return None
    blocks = data.get("blocks")
    if isinstance(blocks, list) and blocks:
        return blocks
    return None


def _load_full_document_blocks(
    source_document_id: str | UUID,
    track: str = "original",
    identifiers: dict[str, str] | None = None,
    known_output_dir: str | None = None,
) -> list[dict] | None:
    """Load structured blocks for a source document from pipeline output.

    Mirrors :func:`_load_full_document_text` but returns the ``blocks``
    array from the JSON (each block has ``type``, ``bbox``, ``page_idx``,
    ``text``, etc.) instead of the concatenated text.
    """
    if known_output_dir:
        result = _load_blocks_from_dir(Path(known_output_dir), track)
        if result:
            return result

    backend_root = Path(__file__).resolve().parents[4]
    doc_id_str = str(source_document_id)

    pipeline_root = backend_root / "data" / "pipeline"
    if pipeline_root.exists():
        for pipeline_dir in pipeline_root.iterdir():
            if not pipeline_dir.is_dir():
                continue
            doc_dir = pipeline_dir / "phase_2" / doc_id_str
            result = _load_blocks_from_dir(doc_dir, track)
            if result:
                return result

    legacy_root = backend_root / "output" / "cross_lingual"
    if legacy_root.exists():
        for lang_dir in legacy_root.iterdir():
            if not lang_dir.is_dir():
                continue
            result = _load_blocks_from_dir(lang_dir / doc_id_str, track)
            if result:
                return result

        if identifiers:
            search_keys = [v.replace("/", "_") for v in identifiers.values() if v]
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


def _markdown_to_blocks(markdown: str) -> list[dict] | None:
    """Parse a markdown document into MinerU-style ContentBlock dicts.

    Used as a last-resort fallback when neither the database nor the
    pipeline output directory contains structured blocks. The resulting
    blocks carry ``type``, ``text``, ``text_level``, and ``img_path``
    (no ``bbox`` — that requires MinerU's PDF parsing), which is enough
    for the frontend ``StructuredBlockRenderer`` to render headings,
    paragraphs, images, and HTML tables with proper formatting.
    """
    if not markdown or not markdown.strip():
        return None
    blocks: list[dict] = []
    lines = markdown.split("\n")
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        # Heading: # / ## / ### ...
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            blocks.append(
                {
                    "type": "title",
                    "text_level": len(heading.group(1)),
                    "text": heading.group(2).strip(),
                    "page_idx": 0,
                }
            )
            i += 1
            continue
        # Image: ![alt](path)
        image = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", stripped)
        if image:
            blocks.append(
                {
                    "type": "image",
                    "img_path": image.group(2).strip(),
                    "image_caption": [image.group(1)] if image.group(1) else [],
                    "page_idx": 0,
                }
            )
            i += 1
            continue
        # HTML table: <table>...</table>
        if stripped.lower().startswith("<table"):
            table_lines = [line]
            i += 1
            while i < n and "</table>" not in lines[i].lower():
                table_lines.append(lines[i])
                i += 1
            if i < n:
                table_lines.append(lines[i])
                i += 1
            blocks.append(
                {
                    "type": "table",
                    "table_body": "\n".join(table_lines),
                    "text": "",
                    "page_idx": 0,
                }
            )
            continue
        # Markdown table: | ... | with separator row
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1].strip()):
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            header_cells = [c.strip() for c in table_lines[0].strip("|").split("|")]
            rows = [[c.strip() for c in tl.strip("|").split("|")] for tl in table_lines[2:]]
            html = "<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in header_cells) + "</tr></thead><tbody>"
            for row in rows:
                html += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            html += "</tbody></table>"
            blocks.append(
                {
                    "type": "table",
                    "table_body": html,
                    "text": "",
                    "page_idx": 0,
                }
            )
            continue
        # List items: - / * / 1.
        if re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            items: list[str] = []
            while i < n and (re.match(r"^[-*]\s+", lines[i].strip()) or re.match(r"^\d+\.\s+", lines[i].strip())):
                items.append(re.sub(r"^[-*]\s+|^\d+\.\s+", "", lines[i].strip()))
                i += 1
            blocks.append(
                {
                    "type": "list",
                    "list_items": items,
                    "text": "\n".join(items),
                    "page_idx": 0,
                }
            )
            continue
        # Blank line: skip
        if not stripped:
            i += 1
            continue
        # Text paragraph: collect contiguous non-blank, non-special lines
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
        blocks.append(
            {
                "type": "text",
                "text": "\n".join(para_lines).strip(),
                "page_idx": 0,
            }
        )
    return blocks if blocks else None


def _load_from_dir(doc_dir: Path, track: str) -> str | None:
    """Try to load and concatenate text from a single document directory."""
    doc_file = doc_dir / f"{track}.json"
    if not doc_file.exists():
        return None
    try:
        with open(doc_file, "r", encoding="utf-8") as f:
            return concat_document_text(json.load(f))
    except Exception:
        logger.warning("Failed to load full {} text from {}", track, doc_file)
        return None


def _parse_translation_alignment(raw: Any) -> list[TranslationAlignmentChunk]:
    """Parse persisted translation alignment chunks."""
    if not isinstance(raw, list):
        return []

    chunks: list[TranslationAlignmentChunk] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            chunks.append(TranslationAlignmentChunk.model_validate(item))
        except ValueError:
            logger.warning("Skipping invalid translation alignment chunk: {}", item)
    return chunks


def _load_translation_alignment_from_dir(doc_dir: Path) -> list[TranslationAlignmentChunk]:
    """Load translation alignment metadata from one persisted document directory."""
    for filename in ("metadata.json", "translated.json"):
        path = doc_dir / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load translation alignment from {}", path)
            continue
        if not isinstance(data, dict):
            continue
        raw = data.get("translation_alignment")
        metadata = data.get("metadata")
        if raw is None and isinstance(metadata, dict):
            raw = metadata.get("translation_alignment")
        chunks = _parse_translation_alignment(raw)
        if chunks:
            return chunks
    return []


def _load_translation_alignment(
    source_document_id: str | UUID,
    raw_metadata: Any,
    identifiers: dict[str, str] | None = None,
    known_output_dir: str | None = None,
) -> list[TranslationAlignmentChunk]:
    """Load validated translation alignment for an evidence detail response."""
    if isinstance(raw_metadata, dict):
        chunks = _parse_translation_alignment(raw_metadata.get("translation_alignment"))
        if chunks:
            return chunks

    if known_output_dir:
        chunks = _load_translation_alignment_from_dir(Path(known_output_dir))
        if chunks:
            return chunks

    backend_root = Path(__file__).resolve().parents[4]
    doc_id_str = str(source_document_id)
    pipeline_root = backend_root / "data" / "pipeline"
    if pipeline_root.exists():
        for pipeline_dir in pipeline_root.iterdir():
            if not pipeline_dir.is_dir():
                continue
            chunks = _load_translation_alignment_from_dir(pipeline_dir / "phase_2" / doc_id_str)
            if chunks:
                return chunks

    legacy_root = backend_root / "output" / "cross_lingual"
    if legacy_root.exists():
        for lang_dir in legacy_root.iterdir():
            if not lang_dir.is_dir():
                continue
            chunks = _load_translation_alignment_from_dir(lang_dir / doc_id_str)
            if chunks:
                return chunks

        if identifiers:
            search_keys = [value.replace("/", "_") for value in identifiers.values() if value]
            for lang_dir in legacy_root.iterdir():
                if not lang_dir.is_dir():
                    continue
                for child in lang_dir.iterdir():
                    if not child.is_dir():
                        continue
                    if child.name in search_keys or child.name.replace("/", "_") in search_keys:
                        chunks = _load_translation_alignment_from_dir(child)
                        if chunks:
                            return chunks

    return []


def _load_full_document_text(
    source_document_id: str | UUID,
    track: str = "original",
    identifiers: dict[str, str] | None = None,
    known_output_dir: str | None = None,
) -> str | None:
    """Load full text content for a source document from pipeline output.

    Searches in order:
    1. ``known_output_dir`` — exact path from pipeline_run_states.state_json.
    2. ``data/pipeline/*/phase_2/{doc_id}/`` — scan current pipeline output.
    3. ``backend/output/cross_lingual/**/`` — legacy output (by UUID or identifiers).

    Returns concatenated text from all blocks, or None if not found.
    """
    # 1. Exact path from persisted pipeline state
    if known_output_dir:
        result = _load_from_dir(Path(known_output_dir), track)
        if result:
            return result

    backend_root = Path(__file__).resolve().parents[4]
    doc_id_str = str(source_document_id)

    # 2. Current pipeline output: data/pipeline/{run_id}/phase_2/{doc_id}/
    pipeline_root = backend_root / "data" / "pipeline"
    if pipeline_root.exists():
        for pipeline_dir in pipeline_root.iterdir():
            if not pipeline_dir.is_dir():
                continue
            doc_dir = pipeline_dir / "phase_2" / doc_id_str
            result = _load_from_dir(doc_dir, track)
            if result:
                return result

    # 3. Legacy output: backend/output/cross_lingual/{lang}/{doc_id}/
    legacy_root = backend_root / "output" / "cross_lingual"
    if legacy_root.exists():
        for lang_dir in legacy_root.iterdir():
            if not lang_dir.is_dir():
                continue
            result = _load_from_dir(lang_dir / doc_id_str, track)
            if result:
                return result

        if identifiers:
            search_keys = [v.replace("/", "_") for v in identifiers.values() if v]
            for lang_dir in legacy_root.iterdir():
                if not lang_dir.is_dir():
                    continue
                for child in lang_dir.iterdir():
                    if not child.is_dir():
                        continue
                    if child.name in search_keys or child.name.replace("/", "_") in search_keys:
                        result = _load_from_dir(child, track)
                        if result:
                            return result

    return None


def _has_text_or_blocks(text: str | None, blocks: list[dict] | None) -> bool:
    """Return whether a document has stored text or structured content blocks."""
    return bool((text and text.strip()) or blocks)


class SearchService:
    """Search evidence cards grouped by group_id, pivoting field-level extractions."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def search_evidence(
        self,
        *,
        gene: str | None = None,
        variant: str | None = None,
        disease: str | None = None,
        pmid: str | None = None,
        doi: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EvidenceSearchResponse:
        """Search evidence with optional filters and DB-level pagination.

        Groups field-level extractions by group_id and pivots them into
        summary rows with gene/variant/disease/classification columns.
        Uses a two-pass approach:
        1. DB-level GROUP BY + OFFSET/LIMIT to get current page group_ids
        2. Fetch details only for those groups (small bounded set)
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy.dialects.postgresql.ext import aggregate_order_by

        group_id_expr = CanonicalEvidenceItem.active_payload["group_id"].astext

        # Build per-filter group_id sets, then intersect (AND across filters).
        # Each filter targets a disjoint field_id domain (gene vs variant vs disease),
        # so they must be queried independently — ANDing them in one WHERE clause
        # would require field_id to match multiple domains simultaneously.
        per_filter_clauses = []
        if gene:
            per_filter_clauses.append(
                and_(
                    CanonicalEvidenceItem.field_id.in_(_GENE_FIELDS),
                    CanonicalEvidenceItem.active_payload["value"].astext.ilike(f"%{gene}%"),
                )
            )
        if variant:
            per_filter_clauses.append(
                and_(
                    CanonicalEvidenceItem.field_id.in_(_VARIANT_FIELDS),
                    CanonicalEvidenceItem.active_payload["value"].astext.ilike(f"%{variant}%"),
                )
            )
        if disease:
            per_filter_clauses.append(
                and_(
                    CanonicalEvidenceItem.field_id.in_(_DISEASE_FIELDS),
                    CanonicalEvidenceItem.active_payload["value"].astext.ilike(f"%{disease}%"),
                )
            )

        if per_filter_clauses:
            matching_group_ids: set[str] | None = None
            for clause in per_filter_clauses:
                filter_stmt = select(group_id_expr).where(clause).group_by(group_id_expr)
                result = await self._session.execute(filter_stmt)
                ids = {row[0] for row in result.all() if row[0]}
                if matching_group_ids is None:
                    matching_group_ids = ids
                else:
                    matching_group_ids &= ids
            if not matching_group_ids:
                return EvidenceSearchResponse(items=[], total=0, page=page, page_size=page_size)
            matching_group_ids = list(matching_group_ids)
        else:
            matching_group_ids = None

        # ── Pass 1: DB-level GROUP BY + pagination ────────────────
        #
        # The inner query aggregates per-group rows. UUID-typed columns
        # (canonical_evidence_id) and status strings (review_status) cannot
        # be reduced with `min()` / `max()` (no PG ordering for UUID), so
        # we capture them as `array_agg(x ORDER BY created_at)` arrays.
        # The outer SELECT indexes those arrays at [1] to pick the oldest
        # row's value as the representative — a form PostgreSQL actually
        # accepts (unlike `CAST(... AS UUID[])[1]`, which is a syntax
        # error because the cast needs parentheses before indexing).
        inner = (
            select(
                group_id_expr.label("group_id"),
                sa_func.count().label("field_count"),
                sa_func.avg(CanonicalEvidenceItem.current_best_confidence).label("avg_confidence"),
                sa_func.array_agg(
                    aggregate_order_by(
                        CanonicalEvidenceItem.canonical_evidence_id,
                        CanonicalEvidenceItem.created_at.asc(),
                    )
                ).label("canonical_ids"),
                CanonicalEvidenceItem.source_document_id.label("source_document_id"),
                sa_func.array_agg(
                    aggregate_order_by(
                        CanonicalEvidenceItem.review_status,
                        CanonicalEvidenceItem.created_at.asc(),
                    )
                ).label("review_statuses"),
                sa_func.max(CanonicalEvidenceItem.created_at).label("created_at"),
            )
            .group_by(
                group_id_expr,
                CanonicalEvidenceItem.source_document_id,
            )
            .having(group_id_expr.isnot(None))
            .having(group_id_expr != "")
        )
        if matching_group_ids is not None:
            inner = inner.where(group_id_expr.in_(matching_group_ids))

        sub = inner.subquery()
        page_query = select(
            sub.c.group_id,
            sub.c.field_count,
            sub.c.avg_confidence,
            sub.c.canonical_ids[1].label("canonical_evidence_id"),
            sub.c.source_document_id,
            sub.c.review_statuses[1].label("review_status"),
            sub.c.created_at,
        )

        # Count total groups
        count_sub = page_query.subquery()
        count_stmt = select(sa_func.count()).select_from(count_sub)
        total = (await self._session.execute(count_stmt)).scalar_one()

        if total == 0:
            return EvidenceSearchResponse(items=[], total=0, page=page, page_size=page_size)

        # Apply pagination
        offset = (page - 1) * page_size
        page_query = page_query.order_by(sub.c.group_id).offset(offset).limit(page_size)
        page_result = await self._session.execute(page_query)
        page_rows = page_result.all()

        if not page_rows:
            return EvidenceSearchResponse(items=[], total=total, page=page, page_size=page_size)

        page_group_ids = [row.group_id for row in page_rows]
        # Build a lookup from the aggregated page data
        page_summary: dict[str, dict] = {}
        for row in page_rows:
            page_summary[row.group_id] = {
                "field_count": row.field_count,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else None,
                "canonical_evidence_id": row.canonical_evidence_id,
                "source_document_id": row.source_document_id,
                "review_status": row.review_status,
                "created_at": row.created_at,
            }

        # ── Pass 2: Fetch detail rows for current page only ───────
        detail_stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
                CanonicalEvidenceItem.created_at,
            )
            .where(group_id_expr.in_(page_group_ids))
            .order_by(group_id_expr, CanonicalEvidenceItem.field_id)
        )
        detail_result = await self._session.execute(detail_stmt)
        detail_rows = detail_result.all()

        # Pivot: extract gene/variant/disease/classification per group
        groups: dict[str, dict] = {}
        for row in detail_rows:
            payload = row.active_payload or {}
            gid = payload.get("group_id", "")
            if not gid:
                continue

            if gid not in groups:
                summary = page_summary.get(gid, {})
                groups[gid] = {
                    "group_id": gid,
                    "source_document_id": summary.get("source_document_id", row.source_document_id),
                    "canonical_evidence_id": summary.get("canonical_evidence_id", row.canonical_evidence_id),
                    "created_at": summary.get("created_at", row.created_at),
                    "review_status": summary.get("review_status", row.review_status),
                    "field_count": summary.get("field_count", 0),
                    "avg_confidence": summary.get("avg_confidence"),
                    "gene": None,
                    "variant": None,
                    "disease": None,
                    "classification": None,
                }

            g = groups[gid]

            field_id = row.field_id
            value = payload.get("value")
            _extract_summary_field(field_id, value, g)

        # Fallback: parse gene/variant from group_id
        for g in groups.values():
            if not g["gene"]:
                g["gene"] = parse_gene_from_group_id(g["group_id"])
            if not g["variant"]:
                g["variant"] = parse_variant_from_group_id(g["group_id"])

        # Batch-load identifiers and titles for current page's documents
        doc_ids = {g["source_document_id"] for g in groups.values()}
        ident_map: dict[str, dict[str, str]] = {}
        title_map: dict[str, str] = {}
        language_map: dict[str, str] = {}
        original_text_map: dict[str, str] = {}
        availability_map: dict[str, dict[str, bool]] = {}
        if doc_ids:
            ident_stmt = select(SourceDocumentIdentifier).where(
                SourceDocumentIdentifier.source_document_id.in_(doc_ids)
            )
            ident_result = await self._session.execute(ident_stmt)
            for ident in ident_result.scalars():
                ident_map.setdefault(str(ident.source_document_id), {})
                ident_map[str(ident.source_document_id)][ident.identifier_type] = ident.identifier_value

            metadata_stmt = select(
                SourceDocument.source_document_id,
                SourceDocument.raw_metadata,
                SourceDocument.original_text,
                SourceDocument.translated_text,
                SourceDocument.original_blocks,
                SourceDocument.translated_blocks,
            ).where(SourceDocument.source_document_id.in_(doc_ids))
            metadata_result = await self._session.execute(metadata_stmt)
            for row in metadata_result.all():
                raw_metadata = row.raw_metadata or {}
                title = _coerce_str(raw_metadata.get("title")) if isinstance(raw_metadata, dict) else None
                if title:
                    title_map[str(row.source_document_id)] = title
                source_language = _extract_source_language(raw_metadata)
                if source_language:
                    language_map[str(row.source_document_id)] = source_language
                original_text = getattr(row, "original_text", None)
                if isinstance(original_text, str) and original_text.strip():
                    original_text_map[str(row.source_document_id)] = original_text
                availability_map[str(row.source_document_id)] = {
                    "has_full_text": _has_text_or_blocks(
                        getattr(row, "original_text", None),
                        getattr(row, "original_blocks", None),
                    ),
                    "has_translation": _has_text_or_blocks(
                        getattr(row, "translated_text", None),
                        getattr(row, "translated_blocks", None),
                    ),
                }

            missing_language_doc_ids = [doc_id for doc_id in doc_ids if str(doc_id) not in language_map]
            if missing_language_doc_ids:
                run_state_stmt = (
                    select(
                        PipelineRunState.source_document_id,
                        PipelineRunState.state_json,
                    )
                    .where(PipelineRunState.source_document_id.in_(missing_language_doc_ids))
                    .order_by(PipelineRunState.created_at.desc())
                )
                run_state_result = await self._session.execute(run_state_stmt)
                for row in run_state_result.all():
                    doc_key = str(row.source_document_id)
                    if doc_key in language_map:
                        continue
                    source_language = _extract_source_language_from_state(row.state_json)
                    if source_language:
                        language_map[doc_key] = source_language

            for doc_id in doc_ids:
                doc_key = str(doc_id)
                if doc_key in language_map:
                    continue
                source_language = _detect_source_language_from_text(original_text_map.get(doc_key))
                if source_language:
                    language_map[doc_key] = source_language

        # Build results (apply PMID/DOI post-filters)
        items: list[EvidenceSearchResult] = []
        filtered_total = total
        for gid in page_group_ids:
            g = groups.get(gid)
            if not g:
                continue

            doc_ident = ident_map.get(str(g["source_document_id"]), {})
            if pmid and pmid not in doc_ident.get("pmid", ""):
                filtered_total -= 1
                continue
            if doi and doi.lower() not in doc_ident.get("doi", "").lower():
                filtered_total -= 1
                continue

            availability = availability_map.get(str(g["source_document_id"]), {})
            items.append(
                EvidenceSearchResult(
                    group_id=g["group_id"],
                    source_document_id=g["source_document_id"],
                    title=title_map.get(str(g["source_document_id"])),
                    pmid=doc_ident.get("pmid"),
                    doi=doc_ident.get("doi"),
                    source_language=language_map.get(str(g["source_document_id"])),
                    gene=g["gene"],
                    variant=g["variant"],
                    disease=g["disease"],
                    classification=g["classification"],
                    field_count=g["field_count"],
                    avg_confidence=g["avg_confidence"],
                    review_status=g["review_status"],
                    canonical_evidence_id=g["canonical_evidence_id"],
                    created_at=g["created_at"],
                    has_full_text=availability.get("has_full_text", False),
                    has_translation=availability.get("has_translation", False),
                )
            )

        return EvidenceSearchResponse(
            items=items,
            total=filtered_total if (pmid or doi) else total,
            page=page,
            page_size=page_size,
        )

    async def get_group_detail(
        self,
        *,
        group_id: str | None = None,
        source_document_id: str | None = None,
    ) -> EvidenceGroupDetailResponse:
        """Return detail payload for one grouped evidence row.

        At least one of *group_id* or *source_document_id* must be given.
        When only *source_document_id* is provided the method picks the
        first ``group_id`` found for that document.  This is required
        because ``group_id`` values are not unique per source document —
        the same ``gene=<G>|variant=<V>`` string can appear across many
        papers.
        """
        conditions: list = []
        if group_id:
            conditions.append(
                CanonicalEvidenceItem.active_payload["group_id"].astext == group_id,
            )
        if source_document_id:
            conditions.append(
                CanonicalEvidenceItem.source_document_id == source_document_id,
            )
        stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
                CanonicalEvidenceItem.updated_at,
            )
            .where(*conditions)
            .order_by(CanonicalEvidenceItem.field_id)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        if not rows:
            raise NoResultFound()

        # Deduplicate by (field_id, track): keep the most recently updated row
        # to avoid "Duplicate track" warnings from the trace-building loop.
        seen: dict[tuple[str, str], int] = {}
        deduped_rows = []
        for row in sorted(rows, key=lambda r: r.updated_at or "", reverse=True):
            track = (row.active_payload or {}).get("track", "original")
            key = (row.field_id, track)
            if key not in seen:
                seen[key] = 1
                deduped_rows.append(row)
        rows = deduped_rows

        # If group_id was not provided, extract it from the first row
        if not group_id:
            group_id = (rows[0].active_payload or {}).get("group_id", "")

        source_document_id = rows[0].source_document_id

        ident_stmt = select(SourceDocumentIdentifier).where(
            SourceDocumentIdentifier.source_document_id == source_document_id
        )
        ident_result = await self._session.execute(ident_stmt)
        identifiers = {ident.identifier_type: ident.identifier_value for ident in ident_result.scalars().all()}
        metadata_stmt = select(
            SourceDocument.raw_metadata,
            SourceDocument.original_text,
            SourceDocument.translated_text,
            SourceDocument.original_blocks,
            SourceDocument.translated_blocks,
        ).where(SourceDocument.source_document_id == source_document_id)
        metadata_result = await self._session.execute(metadata_stmt)
        metadata_row = metadata_result.one_or_none()
        raw_metadata = (metadata_row[0] if metadata_row else None) or {}
        db_original_text: str | None = metadata_row[1] if metadata_row else None
        db_translated_text: str | None = metadata_row[2] if metadata_row else None
        db_original_blocks: list[dict] | None = metadata_row[3] if metadata_row else None
        db_translated_blocks: list[dict] | None = metadata_row[4] if metadata_row else None
        title = _coerce_str(raw_metadata.get("title")) if isinstance(raw_metadata, dict) else None

        # Look up phase_2 output_dir from persisted pipeline state
        phase2_output_dir: str | None = None
        run_state_stmt = (
            select(PipelineRunState.state_json)
            .where(PipelineRunState.source_document_id == source_document_id)
            .order_by(PipelineRunState.created_at.desc())
            .limit(1)
        )
        run_state_result = await self._session.execute(run_state_stmt)
        state_json = run_state_result.scalar_one_or_none()
        if isinstance(state_json, dict):
            p2_output = state_json.get("phase_2_output")
            if isinstance(p2_output, dict):
                phase2_output_dir = p2_output.get("output_dir")

        distribution = EvidenceFieldDistribution()
        detail_items: list[EvidenceGroupItem] = []
        confidences: list[float] = []
        gene = variant = disease = classification = None

        for row in rows:
            payload = row.active_payload or {}
            value = _coerce_str(payload.get("value"))
            field_id = row.field_id
            field_name = payload.get("field_name")
            category = payload.get("category") or _category_from_field_id(field_id)
            track = payload.get("track")
            confidence = float(row.current_best_confidence) if row.current_best_confidence is not None else None
            if confidence is not None:
                confidences.append(confidence)

            if category:
                category_key = str(category)
                distribution.by_category[category_key] = distribution.by_category.get(category_key, 0) + 1
            distribution.by_field[field_id] = distribution.by_field.get(field_id, 0) + 1
            distribution.by_status[row.review_status] = distribution.by_status.get(row.review_status, 0) + 1
            if track:
                track_key = str(track)
                distribution.by_track[track_key] = distribution.by_track.get(track_key, 0) + 1

            if field_id in _GENE_FIELDS and not gene:
                gene = value
            elif field_id in _VARIANT_FIELDS and not variant:
                variant = value
            elif field_id in _DISEASE_FIELDS and not disease:
                disease = value
            elif field_id in _CLASSIFICATION_FIELDS and not classification:
                classification = value

            source_payload = payload.get("source")
            page = source_payload.get("page") if isinstance(source_payload, dict) else None
            detail_items.append(
                EvidenceGroupItem(
                    canonical_evidence_id=row.canonical_evidence_id,
                    field_id=field_id,
                    field_name=str(field_name) if field_name else None,
                    category=str(category) if category else None,
                    value=value,
                    review_status=row.review_status,
                    confidence=confidence,
                    track=str(track) if track else None,
                    page=page if isinstance(page, int) else None,
                )
            )

        # Fallback: parse gene/variant from group_id if field-level extraction missed them
        if not gene and group_id:
            gene = parse_gene_from_group_id(group_id)
        if not variant and group_id:
            variant = parse_variant_from_group_id(group_id)
        # Build traces by matching original/translated pairs per field_id
        items_by_field: dict[str, list] = {}
        for row in rows:
            items_by_field.setdefault(row.field_id, []).append(row)

        traces: list[EvidenceTrackTrace] = []
        for field_id, field_rows in items_by_field.items():
            original_row = None
            translated_row = None
            reconciled_row = None
            for row in field_rows:
                payload = row.active_payload or {}
                track = payload.get("track")
                if track == "original":
                    if original_row is not None:
                        logger.debug(
                            "Duplicate original track for field_id={}: overwriting with canonical_evidence_id={}",
                            field_id,
                            row.canonical_evidence_id,
                        )
                    original_row = row
                elif track == "translated":
                    if translated_row is not None:
                        logger.debug(
                            "Duplicate translated track for field_id={}: overwriting with canonical_evidence_id={}",
                            field_id,
                            row.canonical_evidence_id,
                        )
                    translated_row = row
                elif track == "reconciled":
                    if reconciled_row is None:
                        reconciled_row = row
                else:
                    logger.debug(
                        "Non-standard track value {!r} for field_id={}, "
                        "canonical_evidence_id={} — skipping in trace pairing",
                        track,
                        field_id,
                        row.canonical_evidence_id,
                    )

            # Fall back to reconciled row when no original/translated exist
            if original_row is None and translated_row is None and reconciled_row is not None:
                original_row = reconciled_row

            ref_row = original_row or translated_row or reconciled_row
            if ref_row is None:
                logger.debug(
                    "No usable track found for field_id={} — skipping trace",
                    field_id,
                )
                continue

            original_source = (
                original_row.active_payload.get("source") if original_row and original_row.active_payload else {}
            ) or {}
            translated_source = (
                translated_row.active_payload.get("source") if translated_row and translated_row.active_payload else {}
            ) or {}
            original_value = (
                _coerce_str(original_row.active_payload.get("value"))
                if original_row and original_row.active_payload
                else None
            )
            translated_value = (
                _coerce_str(translated_row.active_payload.get("value"))
                if translated_row and translated_row.active_payload
                else None
            )

            original = _build_highlight(original_source, original_value) if original_source is not None else None
            translated = (
                _build_highlight(translated_source, translated_value) if translated_source is not None else None
            )

            # Fall back to reconciled row's highlight when original/translated
            # sources are non-dict (e.g. "benchmark_ground_truth" strings)
            # and produce no usable highlight.
            if original is None and translated is None and reconciled_row is not None:
                rec_payload = reconciled_row.active_payload or {}
                rec_source = rec_payload.get("source")
                if isinstance(rec_source, dict):
                    rec_value = _coerce_str(rec_payload.get("value"))
                    original = _build_highlight(rec_source, rec_value)
                    original_value = original_value or rec_value

            canonical_id = ref_row.canonical_evidence_id
            field_name = ref_row.active_payload.get("field_name") if ref_row.active_payload else None

            traces.append(
                EvidenceTrackTrace(
                    canonical_evidence_id=canonical_id,
                    field_id=field_id,
                    field_name=str(field_name) if field_name else None,
                    original_value=original_value,
                    translated_value=translated_value,
                    original=original,
                    translated=translated,
                    alignment_confidence=1.0 if original and translated else None,
                )
            )

        loaded_original_text = db_original_text or _load_full_document_text(
            source_document_id,
            track="original",
            identifiers=identifiers,
            known_output_dir=phase2_output_dir,
        )
        loaded_translated_text = db_translated_text or _load_full_document_text(
            source_document_id,
            track="translated",
            identifiers=identifiers,
            known_output_dir=phase2_output_dir,
        )
        loaded_original_blocks = db_original_blocks or _load_full_document_blocks(
            source_document_id,
            track="original",
            identifiers=identifiers,
            known_output_dir=phase2_output_dir,
        )
        loaded_translated_blocks = db_translated_blocks or _load_full_document_blocks(
            source_document_id,
            track="translated",
            identifiers=identifiers,
            known_output_dir=phase2_output_dir,
        )
        original_document_text = _filter_body_text(loaded_original_text)
        translated_document_text = _filter_body_text(loaded_translated_text)
        original_blocks = _filter_body_blocks(loaded_original_blocks, original_document_text)
        translated_blocks = _filter_body_blocks(loaded_translated_blocks, translated_document_text)
        translation_alignment = _load_translation_alignment(
            source_document_id,
            raw_metadata,
            identifiers=identifiers,
            known_output_dir=phase2_output_dir,
        )

        return EvidenceGroupDetailResponse(
            group_id=group_id,
            source_document_id=source_document_id,
            title=title,
            pmid=identifiers.get("pmid"),
            doi=identifiers.get("doi"),
            original_document_text=original_document_text,
            translated_document_text=translated_document_text,
            original_blocks=original_blocks,
            translated_blocks=translated_blocks,
            gene=gene,
            variant=variant,
            disease=disease,
            classification=classification,
            item_count=len(detail_items),
            avg_confidence=(sum(confidences) / len(confidences)) if confidences else None,
            distribution=distribution,
            items=detail_items,
            traces=traces,
            translation_alignment=translation_alignment,
        )
