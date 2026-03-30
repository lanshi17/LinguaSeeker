from src.domain.variant import VariationDataService, get_variation_data_service
from src.services.task_manager import _attempt_hgvs_correction


def attempt_hgvs_correction(source_text: str, translated_text: str) -> tuple[str, bool]:
    return _attempt_hgvs_correction(source_text, translated_text)


__all__ = [
    "VariationDataService",
    "attempt_hgvs_correction",
    "get_variation_data_service",
]
