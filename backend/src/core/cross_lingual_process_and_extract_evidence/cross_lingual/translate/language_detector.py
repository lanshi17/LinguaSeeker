"""Language detection and translation skip logic."""
from __future__ import annotations

import re

from lingua import Language, LanguageDetectorBuilder

_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()

_CJK_RE = re.compile(r"[㐀-鿿぀-ヿ가-힯]")

# Common English words used as a fallback heuristic when the primary
# detector misclassifies heavily-technical ASCII text (e.g. gene mutation
# notation) as Latin or another language.
_EN_WORD_RE = re.compile(
    r"\b(the|and|of|in|to|with|for|on|at|is|are|was|were|be|been|"
    r"has|have|had|by|from|this|that|these|those|not|but|or|as|if|"
    r"when|which|their|there|we|our|patients|mutations|analysis|"
    r"diagnosis|clinical|available|control|collection)\b",
    re.IGNORECASE,
)

_LANG_MAP = {
    Language.ENGLISH: "en",
    Language.CHINESE: "zh",
    Language.JAPANESE: "ja",
    Language.KOREAN: "ko",
    Language.FRENCH: "fr",
    Language.GERMAN: "de",
    Language.SPANISH: "es",
    Language.PORTUGUESE: "pt",
    Language.RUSSIAN: "ru",
    Language.ARABIC: "ar",
}


def detect_language(text: str, sample_size: int = 4000) -> str:
    """Detect the primary language of ``text``.

    Returns ISO 639-1 code (e.g. ``"en"``, ``"zh"``).
    Returns ``"unknown"`` if detection confidence is too low.
    """
    sample = str(text or "").strip()[:sample_size]
    if not sample:
        return "unknown"
    detected = _DETECTOR.detect_language_of(sample)
    if detected is None:
        return "unknown"
    return _LANG_MAP.get(detected, detected.iso_code_639_1.name.lower())


def _looks_english(sample: str) -> bool:
    """Fallback heuristic: does the text contain enough common English words?

    Useful when the primary detector misclassifies technical ASCII text
    (e.g. biomedical mutation notation) as Latin or another language.
    """
    words = _EN_WORD_RE.findall(sample)
    return len(words) >= 3


def should_skip_translation(text: str) -> bool:
    """Return ``True`` if the text is already English or empty."""
    sample = str(text or "").strip()
    if not sample:
        return True
    cjk_count = len(_CJK_RE.findall(sample))
    if cjk_count / len(sample) > 0.05:
        return False
    lang = detect_language(sample)
    if lang == "en":
        return True
    # Fallback: technical English documents (e.g. gene variant tables) may be
    # mis-detected as Latin or other languages.  If the text is predominantly
    # ASCII and contains common English words, treat it as English.
    if sample.isascii() and _looks_english(sample):
        return True
    return False
