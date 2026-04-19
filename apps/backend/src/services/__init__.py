from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.task_manager import (
        init_knowledge_base_if_needed,
        process_literature_identifier_task,
        process_pdf_task,
        process_pubmed_paper_task,
        process_web_page_task,
        resume_supervisor_task,
    )

__all__ = [
    "init_knowledge_base_if_needed",
    "process_literature_identifier_task",
    "process_pdf_task",
    "process_pubmed_paper_task",
    "process_web_page_task",
    "resume_supervisor_task",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from src.services import task_manager

        return getattr(task_manager, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
