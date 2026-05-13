"""Remote MinerU parser via cloud API."""
from __future__ import annotations

from ..mineru_parser import MinerUParser


class MinerURemoteParser(MinerUParser):
    """Remote MinerU parser using the cloud API.

    This is a thin wrapper around MinerUParser that provides a clear
    naming convention for the orchestrator pattern.
    """

    pass
