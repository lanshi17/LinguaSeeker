"""Public pipeline interfaces (layer-agnostic)."""

from .pipeline_step import IPipelineStep, IPipelineContext, IResultAccumulator

__all__ = [
    "IPipelineStep",
    "IPipelineContext",
    "IResultAccumulator",
]
