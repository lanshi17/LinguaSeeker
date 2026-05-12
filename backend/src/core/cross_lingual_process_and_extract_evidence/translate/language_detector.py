"""Language detection and translation skip logic."""
from __future__ import annotations

import re

from lingua import Language, LanguageDetectorBuilder

_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()

_CJK_RE = re.compile(r"[㐀-鿿぀-ヿ가-힯]")

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


def should_skip_translation(text: str) -> bool:
    """Return ``True`` if the text is already English or empty."""
    sample = str(text or "").strip()
    if not sample:
        return True
    if _CJK_RE.search(sample):
        return False
    lang = detect_language(sample)
    return lang == "en"
