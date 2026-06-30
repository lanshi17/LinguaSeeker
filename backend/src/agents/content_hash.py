"""Content hash computation for document processing deduplication.

The hash uniquely identifies a processing request so that identical
submissions can be served from the L1/L2 cache without re-running the
pipeline. The hash incorporates:
  - The source content bytes (for local uploads) or a deterministic
    key derived from identifiers/query (for online acquisition).
  - The extraction target scope key (so the same document processed
    for different gene-disease hypotheses does NOT collide).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import aiofiles

from src.agents.contracts import PipelineGraphState
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import (
    DEFAULT_EXTRACTION_WORKFLOW_MODE,
)


def normalize_identifier(identifier: str) -> str:
    """Normalize literature identifiers consistently across dedup layers."""
    value = identifier.strip().lower()
    return re.sub(r"^(pmid|doi|pmcid)\s*:\s*", "", value)


def compute_hash_from_bytes(content: bytes, scope_key: str | None = None) -> str:
    """Compute a SHA-256 content hash from raw bytes.

    Args:
        content: The document content bytes.
        scope_key: Optional extraction target scope key to namespace the hash.

    Returns:
        A 64-character hex digest string.
    """
    h = hashlib.sha256()
    h.update(content)
    if scope_key:
        h.update(b"\x00")
        h.update(scope_key.encode("utf-8"))
    return h.hexdigest()


def compute_hash_from_text(text: str, scope_key: str | None = None) -> str:
    """Compute a SHA-256 content hash from a text string.

    Used for pre-parsed markdown submissions and online query/identifier keys.

    Args:
        text: The text to hash (query, identifiers, markdown, etc.).
        scope_key: Optional extraction target scope key.

    Returns:
        A 64-character hex digest string.
    """
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    if scope_key:
        h.update(b"\x00")
        h.update(scope_key.encode("utf-8"))
    return h.hexdigest()


async def compute_hash_from_file(file_path: str, scope_key: str | None = None) -> str:
    """Compute a SHA-256 content hash from a file on disk.

    Streams the file in chunks to avoid loading large files into memory.

    Args:
        file_path: Path to the file to hash.
        scope_key: Optional extraction target scope key.

    Returns:
        A 64-character hex digest string.
    """
    h = hashlib.sha256()
    async with aiofiles.open(file_path, "rb") as f:
        while True:
            chunk = await f.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            h.update(chunk)
    if scope_key:
        h.update(b"\x00")
        h.update(scope_key.encode("utf-8"))
    return h.hexdigest()


def _build_online_hash_key(state: PipelineGraphState) -> str | None:
    """Build a deterministic hash key from online acquisition fields.

    Identifiers take priority (query text varies but the same PMID should
    deduplicate). Falls back to the query string.
    """
    if state.identifiers:
        normalized = ",".join(sorted(normalize_identifier(i) for i in state.identifiers if i.strip()))
        return f"identifiers:{normalized}"
    if state.query:
        return f"query:{state.query.strip()}"
    return None


def _get_scope_key(state: PipelineGraphState) -> str | None:
    """Extract the extraction target scope key from state, if present.

    The scope key includes the extraction profile so that the same document
    processed with different profiles does not collide in the cache.  The
    extraction mode is only appended when it differs from the business
    default (``broad``); an explicit ``"catalog"`` rollback therefore gets a
    distinct cache scope, while the default mode produces the normal key.
    """
    parts: list[str] = []
    if state.extraction_target is not None:
        parts.append(state.extraction_target.scope_key)
    if state.extraction_profile and state.extraction_profile != "none":
        parts.append(f"profile={state.extraction_profile}")
    if state.extraction_mode and state.extraction_mode != DEFAULT_EXTRACTION_WORKFLOW_MODE:
        parts.append(f"mode={state.extraction_mode}")
    if state.review_reject_policy and state.review_reject_policy != "hard_veto":
        parts.append(f"review_policy={state.review_reject_policy}")
    return "|".join(parts) if parts else None


async def compute_content_hash(state: PipelineGraphState) -> str | None:
    """Compute the content hash for a pipeline run from its initial state.

    The hash is computed differently depending on the source type:
    - Local upload with a file: hash the file bytes.
    - Local upload with pre-parsed markdown: hash the markdown text.
    - Online acquisition: hash a deterministic key from identifiers/query.

    In all cases, the extraction target scope key is appended to the hash
    so that the same document processed for different targets does not collide.

    Args:
        state: The initial PipelineGraphState (before pipeline execution).

    Returns:
        A 64-character hex digest string, or None if no content is available
        (e.g., phase re-run mode where the content is already known).
    """
    scope_key = _get_scope_key(state)

    # Phase re-run mode: no content to hash (content is from prior run)
    if state.mode.value == "phase":
        return None

    if state.source_type.value == "local":
        if state.upload_file_path:
            path = Path(state.upload_file_path)
            if path.exists():
                return await compute_hash_from_file(state.upload_file_path, scope_key)
        if state.pre_parsed_markdown:
            return compute_hash_from_text(state.pre_parsed_markdown, scope_key)
        return None

    # Online acquisition
    online_key = _build_online_hash_key(state)
    if online_key is None:
        return None
    return compute_hash_from_text(online_key, scope_key)
