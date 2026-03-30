from src.api.routes.core import router as core_router
from src.api.routes.evidence import router as evidence_router
from src.api.routes.stream import router as stream_router
from src.api.routes.task import router as task_router

__all__ = ["core_router", "evidence_router", "stream_router", "task_router"]
