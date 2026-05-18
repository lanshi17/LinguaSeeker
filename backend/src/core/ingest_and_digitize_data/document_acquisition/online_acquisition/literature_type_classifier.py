"""Keyword-based literature type classifier for search results.

Classifies articles into three categories:
- case_report: Case reports, case series, clinical observations
- sequencing: Sequencing studies (NGS, WGS, WES, gene panels)
- functional: Functional studies (in vitro, in vivo, assays, mechanisms)
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional, Sequence

from .contracts import OnlineAcquisitionItem


class LiteratureType(str, Enum):
    CASE_REPORT = "case_report"
    SEQUENCING = "sequencing"
    FUNCTIONAL = "functional"


# --- Keyword patterns (case-insensitive) ---

_CASE_REPORT_PATTERNS = [
    re.compile(r"\bcase\s+report\b", re.IGNORECASE),
    re.compile(r"\bcase\s+series\b", re.IGNORECASE),
    re.compile(r"\bcase\s+stud(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\bclinical\s+case\b", re.IGNORECASE),
    re.compile(r"\bpatient\s+report\b", re.IGNORECASE),
    re.compile(r"\bcase\s+presentation\b", re.IGNORECASE),
]

_CASE_REPORT_JOURNAL_PATTERNS = [
    re.compile(r"\bJ(?:ournal\s+)?Med\s+Case\s+Rep", re.IGNORECASE),
    re.compile(r"\bAm\s+J\s+Case\s+Rep", re.IGNORECASE),
    re.compile(r"\bBMJ\s+Case\s+Rep", re.IGNORECASE),
    re.compile(r"\bCase\s+Rep\b", re.IGNORECASE),
    re.compile(r"\bMedicine\b.*\bcase\b", re.IGNORECASE),
]

_SEQUENCING_PATTERNS = [
    re.compile(r"\b(?:next[\s-]?generation|NGS)\s+sequencing\b", re.IGNORECASE),
    re.compile(r"\bwhole[\s-]?(?:genome|exome)\s+sequencing\b", re.IGNORECASE),
    re.compile(r"\b(?:WGS|WES|WGS/WES)\b"),
    re.compile(r"\btargeted\s+sequencing\b", re.IGNORECASE),
    re.compile(r"\bgene\s+panel\s+(?:sequencing|test|analysis)\b", re.IGNORECASE),
    re.compile(r"\bsequencing\s+(?:analysis|study|data|results)\b", re.IGNORECASE),
    re.compile(r"\b(?:DNA|RNA|genome|genomic|exomic)\s+sequencing\b", re.IGNORECASE),
    re.compile(r"\bmassively\s+parallel\s+sequencing\b", re.IGNORECASE),
    re.compile(r"\bSanger\s+sequencing\b", re.IGNORECASE),
    re.compile(r"\b(?:amplicon|capture|panel)\s+sequencing\b", re.IGNORECASE),
    re.compile(r"\bvariant\s+(?:detection|calling|identification)\s+(?:by|via|using|through)\s+sequencing\b", re.IGNORECASE),
    re.compile(r"\bsequencing[\s-](?:based|method|approach|platform)\b", re.IGNORECASE),
    re.compile(r"\bNGS[\s-](?:based|panel|analysis)\b", re.IGNORECASE),
    re.compile(r"\b(?:Ion\s+Torrent|Illumina|MiSeq|NextSeq|NovaSeq|PacBio|Oxford\s+Nanopore)\b", re.IGNORECASE),
]

_FUNCTIONAL_PATTERNS = [
    re.compile(r"\bin\s+vitro\b", re.IGNORECASE),
    re.compile(r"\bin\s+vivo\b", re.IGNORECASE),
    re.compile(r"\b(?:knockdown|knockdown|knock[\s-]?out|KO|KD)\b", re.IGNORECASE),
    re.compile(r"\boverexpression\b", re.IGNORECASE),
    re.compile(r"\bcell\s+lines?\b", re.IGNORECASE),
    re.compile(r"\b(?:transfected|transfection|transduced)\b", re.IGNORECASE),
    re.compile(r"\bfunctional\s+(?:assay|study|analysis|characterization|validation)\b", re.IGNORECASE),
    re.compile(r"\b(?:luciferase|reporter)\s+assay\b", re.IGNORECASE),
    re.compile(r"\b(?:Western\s+blot|immunoblot|immunoprecipitation|co[\s-]?IP)\b", re.IGNORECASE),
    re.compile(r"\b(?:RT[\s-]?q?PCR|quantitative\s+PCR|real[\s-]?time\s+PCR)\b", re.IGNORECASE),
    re.compile(r"\b(?:apoptosis|proliferation|migration|invasion|viability)\s+(?:assay|test|study)\b", re.IGNORECASE),
    re.compile(r"\bmouse\s+(?:model|xenograft|transgenic)\b", re.IGNORECASE),
    re.compile(r"\btumor\s+(?:growth|formation|suppression)\b", re.IGNORECASE),
    re.compile(r"\bpathogenic(?:ity)?\s+(?:mechanism|study|analysis)\b", re.IGNORECASE),
    re.compile(r"\bprotein\s+(?:function|expression|stability|interaction)\b", re.IGNORECASE),
    re.compile(r"\bmechanis(?:m|tic)\s+stud(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\b(?:CRISPR|Cas9|gene\s+editing)\b", re.IGNORECASE),
    re.compile(r"\b(?:plasmid|vector|construct)\b.*\b(?:express|transfect)\b", re.IGNORECASE),
]


def _match_any(text: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(p.search(text) for p in patterns)


def classify_item(item: OnlineAcquisitionItem) -> Optional[LiteratureType]:
    """Classify a single item by title and journal keywords.

    Returns None if no confident classification can be made.
    """
    title = item.title or ""
    journal = item.journal or ""
    text = f"{title} {journal}"

    # Priority: case report > sequencing > functional
    # Case reports are often co-mentioned with other types; check title specifically
    if _match_any(title, _CASE_REPORT_PATTERNS) or _match_any(journal, _CASE_REPORT_JOURNAL_PATTERNS):
        return LiteratureType.CASE_REPORT

    if _match_any(text, _SEQUENCING_PATTERNS):
        return LiteratureType.SEQUENCING

    if _match_any(text, _FUNCTIONAL_PATTERNS):
        return LiteratureType.FUNCTIONAL

    return None


def classify_items(items: Sequence[OnlineAcquisitionItem]) -> Dict[LiteratureType, List[OnlineAcquisitionItem]]:
    """Classify a list of items and group by type.

    Items that don't match any type are excluded from the result.
    """
    result: Dict[LiteratureType, List[OnlineAcquisitionItem]] = {
        LiteratureType.CASE_REPORT: [],
        LiteratureType.SEQUENCING: [],
        LiteratureType.FUNCTIONAL: [],
    }
    for item in items:
        lit_type = classify_item(item)
        if lit_type is not None:
            result[lit_type].append(item)
    return result


def filter_by_type(
    items: Sequence[OnlineAcquisitionItem],
    types: Sequence[LiteratureType],
) -> List[OnlineAcquisitionItem]:
    """Filter items to only those matching the specified types."""
    type_set = set(types)
    return [item for item in items if classify_item(item) in type_set]
