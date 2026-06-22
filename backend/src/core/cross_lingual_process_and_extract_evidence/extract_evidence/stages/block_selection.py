"""Recall-first block selection for target-scoped evidence extraction."""
from __future__ import annotations

import re
import string
from collections.abc import Sequence
from dataclasses import dataclass

from ..contracts import ContentBlock, ExtractionTarget, TrackDocument
from ..prompts import block_readable_text
from src.utils.text_normalize import normalize_text as _normalize_text
_RELATIONSHIP_CUE_RE = re.compile(
    r"\b("
    r"cause|causes|caused|causative|pathogenic|likely pathogenic|biallelic|monoallelic|"
    r"loss[- ]of[- ]function|deficiency|associated|association|susceptibility|risk|"
    r"uncertain|disputed|refuted|conflicting|not associated|no evidence"
    r")\b",
    re.IGNORECASE,
)
_VARIANT_CUE_RE = re.compile(
    r"("
    r"\bc\.\d+|"
    r"\bp\.[A-Za-z]{1,3}\d+|"
    r"\brs\d+\b|"
    r"\bvariant\b|"
    r"\bmutation\b|"
    r"\bsplice\b|"
    r"\bmissense\b|"
    r"\bnonsense\b|"
    r"\bframeshift\b|"
    r"\bdeletion\b|"
    r"\bduplication\b"
    r")",
    re.IGNORECASE,
)
_SECTION_CUE_RE = re.compile(
    r"\b(title|abstract|result|results|discussion|case report|case presentation|methods)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SelectedBlock:
    """A document block selected for recall-first extraction."""

    index: int
    score: float
    reasons: tuple[str, ...]


def select_recall_first_blocks(
    document: TrackDocument,
    *,
    max_blocks: int = 12,
    disease_aliases: Sequence[str] = (),
) -> tuple[SelectedBlock, ...]:
    """Select high-recall block indices for a target gene-disease extraction task."""
    if max_blocks <= 0 or document.extraction_target is None:
        return ()

    scored = tuple(
        selected
        for index, block in enumerate(document.blocks)
        if (selected := score_block(index, block, document.extraction_target, disease_aliases)) is not None
    )
    if not scored:
        return ()

    expanded = _expand_with_neighbors(scored, document.blocks, max_blocks)
    required_indices = _required_indices(expanded, max_blocks)
    ranked = sorted(
        expanded,
        key=lambda block: (
            0 if block.index in required_indices else 1,
            _selection_priority(block),
            -block.score,
            block.index,
        ),
    )
    return tuple(ranked[:max_blocks])


def _selection_priority(block: SelectedBlock) -> int:
    """Rank target evidence above neighbors, and neighbors above unrelated cues."""
    if "target_gene" in block.reasons or "target_disease" in block.reasons:
        return 0
    if "target_neighbor" in block.reasons:
        return 1
    return 2


def score_block(
    index: int,
    block: ContentBlock,
    target: ExtractionTarget,
    disease_aliases: Sequence[str] = (),
) -> SelectedBlock | None:
    """Score one block for target-scoped recall."""
    text = block_readable_text(block)
    if not text:
        return None

    normalized_text = _normalize_text(text)
    reasons: list[str] = []
    score = 0.0

    if _contains_gene_symbol(text, target.gene_symbol):
        score += 6.0
        reasons.append("target_gene")

    has_target_disease = _contains_any_alias(normalized_text, _disease_aliases(target.disease_name, disease_aliases))
    if has_target_disease:
        score += 5.0
        reasons.append("target_disease")
    elif _contains_disease_family(normalized_text, target.disease_name):
        score += 0.75
        reasons.append("disease_family")

    if _RELATIONSHIP_CUE_RE.search(text):
        score += 2.0
        reasons.append("relationship_cue")

    if _VARIANT_CUE_RE.search(text):
        score += 1.5
        reasons.append("variant_or_pathogenic_cue")

    if _is_table_or_caption(block):
        score += 1.25
        reasons.append("table_or_caption")

    if _has_section_cue(block, text):
        score += 0.75
        reasons.append("section_cue")

    if not reasons:
        return None
    return SelectedBlock(index=index, score=round(score, 4), reasons=tuple(reasons))


def _expand_with_neighbors(
    scored: tuple[SelectedBlock, ...],
    blocks: Sequence[ContentBlock],
    max_blocks: int,
) -> tuple[SelectedBlock, ...]:
    """Add immediate neighbors around target blocks while respecting max_blocks."""
    by_index = {block.index: block for block in scored}
    target_blocks = [
        block for block in scored
        if "target_gene" in block.reasons or "target_disease" in block.reasons
    ]
    for block in sorted(target_blocks, key=lambda item: (-item.score, item.index)):
        for neighbor_index in (block.index - 1, block.index + 1):
            if (
                neighbor_index < 0
                or neighbor_index >= len(blocks)
                or neighbor_index in by_index
                or not block_readable_text(blocks[neighbor_index])
            ):
                continue
            by_index[neighbor_index] = SelectedBlock(
                index=neighbor_index,
                score=0.1,
                reasons=("target_neighbor",),
            )
    return tuple(by_index.values())


def _required_indices(blocks: tuple[SelectedBlock, ...], max_blocks: int) -> set[int]:
    """Keep critical target-gene blocks even under a tight cap."""
    target_gene_blocks = [block for block in blocks if "target_gene" in block.reasons]
    if target_gene_blocks:
        return {block.index for block in target_gene_blocks}

    target_disease_blocks = [block for block in blocks if "target_disease" in block.reasons]
    if target_disease_blocks:
        return {block.index for block in sorted(target_disease_blocks, key=lambda block: -block.score)[:max_blocks]}

    return set()


def _contains_gene_symbol(text: str, gene_symbol: str) -> bool:
    symbol = gene_symbol.strip()
    if not symbol:
        return False
    pattern = re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    return bool(pattern.search(text))


def _contains_any_alias(normalized_text: str, aliases: tuple[str, ...]) -> bool:
    return any(alias and alias in normalized_text for alias in aliases)


def _contains_disease_family(normalized_text: str, disease_name: str) -> bool:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", disease_name.casefold())
        if len(token) > 2 and not token.isdigit()
    ]
    if len(tokens) < 3:
        return False
    matched = sum(1 for token in tokens if token in normalized_text)
    return matched >= min(len(tokens), 4)


def _disease_aliases(disease_name: str, extra_aliases: Sequence[str]) -> tuple[str, ...]:
    candidates = [
        disease_name,
        disease_name.casefold(),
        _remove_parentheticals(disease_name),
        _strip_punctuation(disease_name),
        *extra_aliases,
    ]
    aliases: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_text(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        aliases.append(normalized)
    return tuple(aliases)


def _is_table_or_caption(block: ContentBlock) -> bool:
    return (
        block.type == "table"
        or bool(block.table_body.strip())
        or bool(block.table_caption)
        or bool(block.image_caption)
        or bool(block.chart_caption)
    )


def _has_section_cue(block: ContentBlock, text: str) -> bool:
    if block.type.casefold() in {"title", "abstract", "header"}:
        return True
    return bool(_SECTION_CUE_RE.search(text))




def _remove_parentheticals(value: str) -> str:
    return re.sub(r"\([^)]*\)", "", value)


def _strip_punctuation(value: str) -> str:
    translation = str.maketrans({char: " " for char in string.punctuation})
    return value.translate(translation)
