from src.core.cross_lingual_process_and_extract_evidence.translate.language_detector import (
    detect_language,
    should_skip_translation,
)


def test_detect_english():
    lang = detect_language("The patient presented with a novel variant in the BRCA1 gene.")
    assert lang == "en"


def test_detect_chinese():
    lang = detect_language("该患者携带BRCA1基因的新变异。")
    assert lang == "zh"


def test_detect_japanese():
    lang = detect_language("患者はBRCA1遺伝子の新規変異を呈した。")
    assert lang == "ja"


def test_skip_translation_for_english():
    assert should_skip_translation("This is an English document about genetics.") is True


def test_no_skip_for_chinese():
    assert should_skip_translation("这是一份关于遗传学的中文文档。") is False


def test_skip_translation_for_empty():
    assert should_skip_translation("") is True
    assert should_skip_translation("   ") is True
