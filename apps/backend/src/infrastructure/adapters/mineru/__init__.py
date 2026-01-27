# init-mineru-adapter
from .mineru_impl import MinerUImpl
from .mineru_interface import MinerUInterface
from .mineru_mapping import ERROR_CODE_MAPPING

# 提供一个别名供外部使用
MinerUAdapter = MinerUImpl

__all__ = ["MinerUImpl", "MinerUInterface", "MinerUAdapter", "ERROR_CODE_MAPPING"]



