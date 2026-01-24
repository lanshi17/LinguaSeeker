"""Language value object."""

from enum import Enum


class Language(str, Enum):
    """Supported language codes."""

    CHINESE = "zh"
    JAPANESE = "ja"
    ENGLISH = "en"
    RUSSIAN = "ru"
    GERMAN = "de"
    FRENCH = "fr"

    @classmethod
    def is_supported(cls, lang: str) -> bool:
        """Check if language is supported."""
        return lang in {item.value for item in cls}

    @classmethod
    def from_detected_code(cls, code: str) -> "Language":
        """Convert langdetect code to Language enum.

        Args:
            code: langdetect language code (e.g., 'zh-cn', 'ja')

        Returns:
            Language enum value

        Raises:
            ValueError: If language is not supported
        """
        mapping = {
            "zh-cn": cls.CHINESE,
            "zh-tw": cls.CHINESE,
            "zh": cls.CHINESE,
            "ja": cls.JAPANESE,
            "en": cls.ENGLISH,
            "ru": cls.RUSSIAN,
            "de": cls.GERMAN,
            "fr": cls.FRENCH,
        }
        if code not in mapping:
            raise ValueError(f"Unsupported language: {code}")
        return mapping[code]
