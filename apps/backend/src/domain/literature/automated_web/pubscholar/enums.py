# src/domain/literature/pubscholar/enums.py
from enum import Enum


class Language(str, Enum):
    """Supported languages for paper search."""

    CHINESE = "中文"
    ENGLISH = "英文"


class PaperType(str, Enum):
    """Supported paper types for filtering."""

    JOURNAL = "期刊"
    PREPRINT = "预印本"
    CONFERENCE = "会议"
