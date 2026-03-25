from typing import Any, List

from src.services import task_manager as tasks_module


class _RecordingPostgres:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: List[dict[str, Any]] = []

    def create_sentence_alignment(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("db write failed")


def test_build_sentence_alignments_preserves_offsets() -> None:
    source_text = "第一句。\n第二句。"
    en_text = "Sentence one.\nSentence two."

    alignments = tasks_module._build_sentence_alignments(source_text, en_text)

    assert alignments == [
        {
            "source_sentence": "第一句。",
            "en_sentence": "Sentence one.",
            "source_start": 0,
            "source_end": 4,
            "en_start": 0,
            "en_end": 13,
        },
        {
            "source_sentence": "第二句。",
            "en_sentence": "Sentence two.",
            "source_start": 5,
            "source_end": 9,
            "en_start": 14,
            "en_end": 27,
        },
    ]


def test_persist_alignments_and_warnings_detects_hgvs_autocorrect_failure() -> None:
    postgres = _RecordingPostgres()
    source_text = "Variant c.123A>G was reported."
    en_text = "The variant was reported without exact notation."

    warnings = tasks_module._persist_alignments_and_warnings(
        postgres,
        paper_task_id="paper-1",
        source_text=source_text,
        en_text=en_text,
    )

    assert len(postgres.calls) == 1
    assert warnings == ["HGVS_AUTOCORRECT_FAILED"]


def test_persist_alignments_and_warnings_emits_alignment_persist_failed_once() -> None:
    postgres = _RecordingPostgres(fail=True)
    source_text = "第一句。\n第二句。"
    en_text = "Sentence one.\nSentence two."

    warnings = tasks_module._persist_alignments_and_warnings(
        postgres,
        paper_task_id="paper-2",
        source_text=source_text,
        en_text=en_text,
        base_warnings=["EXISTING_WARNING"],
    )

    assert len(postgres.calls) == 2
    assert warnings == ["EXISTING_WARNING", "ALIGNMENT_PERSIST_FAILED"]
