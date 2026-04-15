from __future__ import annotations

from difflib import SequenceMatcher
import re

from lingua import Language, LanguageDetectorBuilder

_DETECTOR = LanguageDetectorBuilder.from_languages(
    Language.ENGLISH,
    Language.CHINESE,
    Language.JAPANESE,
    Language.KOREAN,
).build()

_CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")



def should_skip_translation(text: str) -> bool:
    sample = str(text or "").strip()
    if not sample:
        return False
    if _CJK_RE.search(sample):
        return False
    detected = _DETECTOR.detect_language_of(sample[:4000])
    return detected == Language.ENGLISH



def validate_translation_output(source_text: str, translated_text: str) -> None:
    source = str(source_text or "").strip()
    translated = str(translated_text or "").strip()
    if not translated:
        raise ValueError("translation_validation_failed: empty")
    if _CJK_RE.search(translated):
        raise ValueError("translation_validation_failed: non_english_output")
    ratio = SequenceMatcher(None, source.lower(), translated.lower()).ratio()
    if source and ratio >= 0.85:
        raise ValueError("translation_validation_failed: unchanged")
    detected = _DETECTOR.detect_language_of(translated[:4000])
    if detected not in {None, Language.ENGLISH}:
        raise ValueError("translation_validation_failed: non_english_output")
