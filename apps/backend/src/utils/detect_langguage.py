# 语言检测工具 (基于 lingua)
from __future__ import annotations

from typing import Dict, List

from lingua import Language, LanguageDetector, LanguageDetectorBuilder

from src.utils.logger import Logger

logger = Logger.get_logger("LanguageDetector")
DEFAULT_LANGUAGES: List[str] = ["en"]

# MinerU 语言映射表
LANGUAGE_MAPPING: Dict[Language, List[str]] = {
    Language.CHINESE: ["ch"],
    Language.ENGLISH: ["en"],
    Language.JAPANESE: ["ja"],
    Language.GERMAN: ["de"],
    Language.FRENCH: ["fr"],
    Language.RUSSIAN: ["ru"],
}

def _build_detector() -> LanguageDetector | None:
    try:
        supported_languages = list(LANGUAGE_MAPPING.keys())
        if not supported_languages:
            logger.warning("No languages configured for Lingua detector, falling back to defaults")
            return None
        return LanguageDetectorBuilder.from_languages(*supported_languages).build()
    except Exception as exc:
        logger.error("Failed to initialize Lingua detector ({})", exc)
        return None

_DETECTOR: LanguageDetector | None = _build_detector()

def detect_language(text_snippet: str) -> List[str]:
    normalized_snippet = (text_snippet or "").replace("\n", " ").strip()
    if not normalized_snippet:
        logger.warning("Empty text snippet for language detection, defaulting to {}", DEFAULT_LANGUAGES)
        return DEFAULT_LANGUAGES

    if _DETECTOR is None:
        logger.warning("Lingua detector is unavailable, defaulting to {}", DEFAULT_LANGUAGES)
        return DEFAULT_LANGUAGES

    try:
        detected_language = _DETECTOR.detect_language_of(normalized_snippet)
    except Exception as exc:
        logger.error("Language detection failed ({}), falling back to {}", exc, DEFAULT_LANGUAGES)
        return DEFAULT_LANGUAGES

    if not detected_language:
        logger.warning("Lingua could not determine language, defaulting to {}", DEFAULT_LANGUAGES)
        return DEFAULT_LANGUAGES

    mineru_languages = LANGUAGE_MAPPING.get(detected_language)
    if not mineru_languages:
        logger.info("Detected unsupported language {}, defaulting to {}", detected_language, DEFAULT_LANGUAGES)
        return DEFAULT_LANGUAGES

    return mineru_languages
